from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..supabase_client import get_admin_client

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def rebuild_schedule() -> None:
    """
    Reads all user profiles from the DB and re-creates one daily cron job per user.
    Called on startup and whenever a user changes their delivery_hour_utc.
    """
    sb = get_admin_client()
    result = sb.table("profiles").select("user_id, delivery_hour_utc").execute()
    profiles = result.data or []

    # Remove all existing pipeline jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("pipeline_"):
            scheduler.remove_job(job.id)

    for row in profiles:
        user_id = row["user_id"]
        hour = row["delivery_hour_utc"]
        scheduler.add_job(
            _run_for_user,
            CronTrigger(hour=hour, minute=0),
            args=[user_id],
            id=f"pipeline_{user_id}",
            replace_existing=True,
            misfire_grace_time=3600,  # run up to 1h late if the server was restarting
        )

    logger.info("Scheduler rebuilt: %d user job(s) scheduled.", len(profiles))


async def _run_for_user(user_id: str) -> None:
    """Async wrapper so APScheduler can call the synchronous runner in a thread."""
    import asyncio
    from .runner import run_pipeline_for_user
    await asyncio.to_thread(run_pipeline_for_user, user_id)
