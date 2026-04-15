from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..dependencies import CurrentUser
from ..models import ProfileSettings, SettingsPatch
from ..supabase_client import get_admin_client

router = APIRouter(prefix="/settings", tags=["settings"])

# Features that require a paid tier
_PAID_FIELDS = {"arxiv_categories", "elevenlabs_voice_id", "delivery_hour_utc"}


@router.get("", response_model=ProfileSettings)
async def get_settings(user_id: CurrentUser) -> ProfileSettings:
    sb = get_admin_client()
    row = sb.table("profiles").select("*").eq("user_id", user_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    d = row.data
    return ProfileSettings(
        focus_text=d["focus_text"],
        arxiv_categories=d["arxiv_categories"],
        relevance_threshold=d["relevance_threshold"],
        elevenlabs_voice_id=d["elevenlabs_voice_id"],
        delivery_hour_utc=d["delivery_hour_utc"],
    )


@router.patch("", response_model=ProfileSettings)
async def patch_settings(body: SettingsPatch, user_id: CurrentUser) -> ProfileSettings:
    sb = get_admin_client()

    # Check tier for paid-only fields
    attempted_paid = {f for f in _PAID_FIELDS if getattr(body, f, None) is not None}
    if attempted_paid:
        user_row = sb.table("users").select("tier").eq("id", user_id).single().execute()
        if user_row.data and user_row.data["tier"] != "paid":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "upgrade_required",
                    "feature": next(iter(attempted_paid)),
                },
            )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await get_settings(user_id)

    sb.table("profiles").update(updates).eq("user_id", user_id).execute()

    # If delivery_hour changed, rebuild the APScheduler schedule
    if "delivery_hour_utc" in updates:
        from ..pipeline.scheduler import rebuild_schedule
        await rebuild_schedule()

    return await get_settings(user_id)
