from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    briefai_claude_model: str = "claude-sonnet-4-6"

    # OpenAI
    openai_api_key: str

    # ElevenLabs
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"

    # Supabase
    supabase_url: str
    supabase_service_key: str          # service role key — backend only, never sent to client
    supabase_jwt_secret: str           # from Supabase project settings → API → JWT Secret
    supabase_bucket: str = "briefs"

    # RevenueCat
    revenuecat_webhook_secret: str | None = None

    # arXiv defaults (used as fallback when a user profile has no custom categories)
    arxiv_categories_default: str = "cs.LG,cs.AR,eess.SP"
    relevance_threshold_default: float = 0.72


settings = Settings()  # type: ignore[call-arg]
