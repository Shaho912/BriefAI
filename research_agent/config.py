from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass
class ResearchConfig:
    anthropic_api_key: str
    openai_api_key: str
    claude_model: str
    arxiv_categories: list[str]
    relevance_threshold: float
    output_dir: Path
    # Phase 4 — optional delivery fields
    elevenlabs_api_key: str | None
    elevenlabs_voice_id: str
    supabase_url: str | None
    supabase_service_key: str | None
    supabase_bucket: str
    pushover_api_token: str | None
    pushover_user_key: str | None


def load_research_config(
    output_dir: str | None = None,
) -> ResearchConfig:
    load_dotenv()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise ConfigError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file — required for paper scoring."
        )

    raw_categories = os.getenv("ARXIV_CATEGORIES", "cs.LG,cs.AR,eess.SP")
    categories = [c.strip() for c in raw_categories.split(",") if c.strip()]

    try:
        threshold = float(os.getenv("RELEVANCE_THRESHOLD", "0.72"))
    except ValueError:
        threshold = 0.72

    return ResearchConfig(
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        claude_model=os.getenv("BRIEFAI_CLAUDE_MODEL", "claude-sonnet-4-6"),
        arxiv_categories=categories,
        relevance_threshold=threshold,
        output_dir=Path(output_dir or os.getenv("BRIEFAI_OUTPUT_DIR", "./output")),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", "").strip() or None,
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
        supabase_url=os.getenv("SUPABASE_URL", "").strip() or None,
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", "").strip() or None,
        supabase_bucket=os.getenv("SUPABASE_BUCKET", "briefs"),
        pushover_api_token=os.getenv("PUSHOVER_API_TOKEN", "").strip() or None,
        pushover_user_key=os.getenv("PUSHOVER_USER_KEY", "").strip() or None,
    )
