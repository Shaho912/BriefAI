from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, briefs, onboarding, settings as settings_api, subscriptions, webhooks
from .pipeline.scheduler import rebuild_schedule, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: build the per-user schedule and start APScheduler
    await rebuild_schedule()
    scheduler.start()
    logger.info("APScheduler started.")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped.")


app = FastAPI(title="BriefAI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your domain before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(settings_api.router)
app.include_router(briefs.router)
app.include_router(subscriptions.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
