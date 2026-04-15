from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..dependencies import CurrentUser
from ..models import PushTokenRequest, UserMe
from ..supabase_client import get_admin_client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserMe)
async def get_me(user_id: CurrentUser) -> UserMe:
    sb = get_admin_client()
    row = sb.table("users").select("*").eq("id", user_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    d = row.data
    return UserMe(
        id=d["id"],
        email=d["email"],
        display_name=d.get("display_name"),
        tier=d["tier"],
        created_at=d["created_at"],
    )


@router.put("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def update_push_token(body: PushTokenRequest, user_id: CurrentUser) -> None:
    sb = get_admin_client()
    sb.table("users").update({"expo_push_token": body.expo_push_token}).eq("id", user_id).execute()
