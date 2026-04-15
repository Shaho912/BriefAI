from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status

from ..config import settings
from ..dependencies import CurrentUser
from ..models import BriefDetail, BriefsPage, BriefSummary
from ..supabase_client import get_admin_client

router = APIRouter(prefix="/briefs", tags=["briefs"])

_SIGNED_URL_TTL = 3600  # 1 hour


def _sign_audio_url(storage_path: str | None) -> str | None:
    if not storage_path:
        return None
    sb = get_admin_client()
    result = (
        sb.storage.from_(settings.supabase_bucket)
        .create_signed_url(storage_path, _SIGNED_URL_TTL)
    )
    return result.get("signedURL") if isinstance(result, dict) else None


@router.get("", response_model=BriefsPage)
async def list_briefs(
    user_id: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BriefsPage:
    sb = get_admin_client()

    # Free tier: cap history to 7 days
    user_row = sb.table("users").select("tier").eq("id", user_id).single().execute()
    tier = user_row.data["tier"] if user_row.data else "free"

    query = sb.table("briefs").select("id, arxiv_id, title, relevance_score, generated_at, storage_path", count="exact")
    query = query.eq("user_id", user_id).order("generated_at", desc=True)

    if tier == "free":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        query = query.gte("generated_at", cutoff)

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).execute()

    items = [
        BriefSummary(
            id=row["id"],
            arxiv_id=row["arxiv_id"],
            title=row["title"],
            relevance_score=row["relevance_score"],
            generated_at=row["generated_at"],
            audio_url=_sign_audio_url(row.get("storage_path")),
        )
        for row in (result.data or [])
    ]

    return BriefsPage(
        items=items,
        total=result.count or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/latest", response_model=BriefDetail)
async def get_latest_brief(user_id: CurrentUser) -> BriefDetail:
    sb = get_admin_client()
    result = (
        sb.table("briefs")
        .select("*")
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No briefs found.")
    return _row_to_detail(result.data[0])


@router.get("/{brief_id}", response_model=BriefDetail)
async def get_brief(brief_id: str, user_id: CurrentUser) -> BriefDetail:
    sb = get_admin_client()
    result = (
        sb.table("briefs")
        .select("*")
        .eq("id", brief_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief not found.")
    return _row_to_detail(result.data)


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(user_id: CurrentUser) -> dict:
    """Manually trigger a pipeline run. Paid tier only."""
    # TODO: re-enable paid gate before App Store submission
    # sb = get_admin_client()
    # user_row = sb.table("users").select("tier").eq("id", user_id).single().execute()
    # if not user_row.data or user_row.data["tier"] != "paid":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail={"error": "upgrade_required", "feature": "manual_trigger"},
    #     )

    from backend.pipeline.runner import run_pipeline_for_user
    asyncio.create_task(asyncio.to_thread(run_pipeline_for_user, user_id, True))
    return {"message": "Pipeline triggered. Your brief will be ready shortly."}


def _row_to_detail(row: dict) -> BriefDetail:
    return BriefDetail(
        id=row["id"],
        arxiv_id=row["arxiv_id"],
        title=row["title"],
        authors=row.get("authors", []),
        relevance_score=row["relevance_score"],
        brief_text=row["brief_text"],
        audio_url=_sign_audio_url(row.get("storage_path")),
        generated_at=row["generated_at"],
    )
