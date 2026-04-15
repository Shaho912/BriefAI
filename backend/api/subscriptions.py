from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import CurrentUser
from ..models import SubscriptionStatus
from ..supabase_client import get_admin_client

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(user_id: CurrentUser) -> SubscriptionStatus:
    sb = get_admin_client()
    user_row = sb.table("users").select("tier").eq("id", user_id).single().execute()
    tier = user_row.data["tier"] if user_row.data else "free"

    sub_row = sb.table("subscriptions").select("status, expires_at").eq("user_id", user_id).execute()
    if sub_row.data:
        sub = sub_row.data[0]
        return SubscriptionStatus(
            tier=tier,
            status=sub["status"],
            expires_at=sub.get("expires_at"),
        )

    return SubscriptionStatus(tier=tier, status="inactive", expires_at=None)
