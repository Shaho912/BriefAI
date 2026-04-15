from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserMe(BaseModel):
    id: str
    email: str
    display_name: str | None
    tier: Literal["free", "paid"]
    created_at: datetime


class PushTokenRequest(BaseModel):
    expo_push_token: str


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    pass  # no body needed — user_id comes from JWT


class SessionCreated(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class SessionDetail(BaseModel):
    session_id: str
    status: Literal["in_progress", "complete"]
    messages: list[dict]
    created_at: datetime


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class ProfileSettings(BaseModel):
    focus_text: str
    arxiv_categories: list[str]
    relevance_threshold: float
    elevenlabs_voice_id: str
    delivery_hour_utc: int


class SettingsPatch(BaseModel):
    arxiv_categories: list[str] | None = None
    relevance_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    elevenlabs_voice_id: str | None = None
    delivery_hour_utc: int | None = Field(default=None, ge=0, le=23)


# ---------------------------------------------------------------------------
# Briefs
# ---------------------------------------------------------------------------

class BriefSummary(BaseModel):
    id: str
    arxiv_id: str
    title: str
    relevance_score: float
    generated_at: datetime
    audio_url: str | None


class BriefDetail(BaseModel):
    id: str
    arxiv_id: str
    title: str
    authors: list[str]
    relevance_score: float
    brief_text: str
    audio_url: str | None        # signed URL (1hr TTL)
    generated_at: datetime


class BriefsPage(BaseModel):
    items: list[BriefSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class SubscriptionStatus(BaseModel):
    tier: Literal["free", "paid"]
    status: str
    expires_at: datetime | None
