from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..config import settings
from ..supabase_client import get_admin_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# RevenueCat event types that indicate an active subscription
_ACTIVE_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE", "UNCANCELLATION"}
_INACTIVE_EVENTS = {"EXPIRATION", "CANCELLATION", "BILLING_ISSUE"}


@router.post("/revenuecat", status_code=status.HTTP_200_OK)
async def revenuecat_webhook(request: Request) -> dict:
    body = await request.body()

    # Validate webhook signature if secret is configured
    if settings.revenuecat_webhook_secret:
        auth_header = request.headers.get("Authorization", "")
        expected = settings.revenuecat_webhook_secret
        if not hmac.compare_digest(auth_header, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    payload = await request.json()
    event = payload.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id")
    expires_at = event.get("expiration_at_ms")

    if not app_user_id:
        return {"status": "ignored", "reason": "no app_user_id"}

    sb = get_admin_client()

    if event_type in _ACTIVE_EVENTS:
        new_tier = "paid"
        sub_status = "active"
    elif event_type in _INACTIVE_EVENTS:
        new_tier = "free"
        sub_status = "inactive"
    else:
        return {"status": "ignored", "reason": f"unhandled event type: {event_type}"}

    # Look up user by RevenueCat app_user_id
    sub_row = (
        sb.table("subscriptions")
        .select("user_id")
        .eq("revenuecat_app_user_id", app_user_id)
        .single()
        .execute()
    )
    if not sub_row.data:
        logger.warning("RevenueCat webhook: no subscription row for app_user_id=%s", app_user_id)
        return {"status": "ignored", "reason": "user not found"}

    user_id = sub_row.data["user_id"]

    # Update subscription record
    sb.table("subscriptions").update({
        "status": sub_status,
        "product_id": product_id,
        "expires_at": (
            __import__("datetime").datetime.fromtimestamp(
                expires_at / 1000, tz=__import__("datetime").timezone.utc
            ).isoformat()
            if expires_at else None
        ),
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }).eq("user_id", user_id).execute()

    # Update user tier
    sb.table("users").update({"tier": new_tier}).eq("id", user_id).execute()

    logger.info("RevenueCat: user=%s tier=%s event=%s", user_id, new_tier, event_type)
    return {"status": "ok"}
