from __future__ import annotations

"""
Per-user pipeline runner — multi-user adaptation of run_pipeline.py.

Called by APScheduler daily and by POST /briefs/trigger.
All pipeline modules (fetcher, scorer, selector, generator, tts) are reused unchanged;
this module replaces the file-based config/state with Supabase DB reads/writes.
"""

import logging
import urllib.error
import urllib.request
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from openai import OpenAI

from research_agent.config import ResearchConfig
from research_agent.fetcher import ArxivFetcher
from research_agent.profile import ResearchProfile
from research_agent.scorer import PaperScorer
from research_agent.selector import PaperSelector
from brief_agent.generator import BriefGenerator
from ..config import settings
from ..supabase_client import get_admin_client

logger = logging.getLogger(__name__)

_FREE_TIER_WEEKLY_LIMIT = 3
_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


@dataclass
class _UserContext:
    user_id: str
    tier: str
    expo_push_token: str | None
    focus_text: str
    embedding: list[float]
    arxiv_categories: list[str]
    relevance_threshold: float
    elevenlabs_voice_id: str
    delivery_hour_utc: int


def run_pipeline_for_user(user_id: str, force: bool = False) -> None:
    """Entry point for APScheduler and the manual trigger endpoint."""
    logger.info("Pipeline starting for user=%s", user_id)
    sb = get_admin_client()

    # ------------------------------------------------------------------
    # Load user context from DB
    # ------------------------------------------------------------------
    user_row = sb.table("users").select("tier, expo_push_token").eq("id", user_id).single().execute()
    if not user_row.data:
        logger.error("User %s not found — aborting.", user_id)
        return

    profile_row = (
        sb.table("profiles")
        .select("focus_text, embedding, arxiv_categories, relevance_threshold, elevenlabs_voice_id, delivery_hour_utc")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not profile_row.data:
        logger.warning("No profile for user %s — aborting.", user_id)
        return

    raw_embedding = profile_row.data["embedding"]
    embedding: list[float] = json.loads(raw_embedding) if isinstance(raw_embedding, str) else raw_embedding

    ctx = _UserContext(
        user_id=user_id,
        tier=user_row.data["tier"],
        expo_push_token=user_row.data.get("expo_push_token"),
        focus_text=profile_row.data["focus_text"],
        embedding=embedding,
        arxiv_categories=profile_row.data["arxiv_categories"],
        relevance_threshold=profile_row.data["relevance_threshold"],
        elevenlabs_voice_id=profile_row.data["elevenlabs_voice_id"],
        delivery_hour_utc=profile_row.data["delivery_hour_utc"],
    )

    # ------------------------------------------------------------------
    # Free tier gate: max 3 briefs per week
    # ------------------------------------------------------------------
    if ctx.tier == "free":
        week_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        count_result = (
            sb.table("briefs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("generated_at", week_start)
            .execute()
        )
        if (count_result.count or 0) >= _FREE_TIER_WEEKLY_LIMIT:
            logger.info("User %s hit free tier limit (%d/week) — skipping.", user_id, _FREE_TIER_WEEKLY_LIMIT)
            return

    # ------------------------------------------------------------------
    # Load seen papers from DB
    # ------------------------------------------------------------------
    seen_result = sb.table("seen_papers").select("arxiv_id").eq("user_id", user_id).execute()
    seen_ids: set[str] = {row["arxiv_id"] for row in (seen_result.data or [])}

    # ------------------------------------------------------------------
    # Build a ResearchConfig-compatible object from DB values
    # The existing pipeline modules accept ResearchConfig; we build one here.
    # ------------------------------------------------------------------
    import tempfile, os
    tmp_output = Path(tempfile.mkdtemp())

    config = ResearchConfig(
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        claude_model=settings.briefai_claude_model,
        arxiv_categories=ctx.arxiv_categories,
        relevance_threshold=ctx.relevance_threshold,
        output_dir=tmp_output,
        elevenlabs_api_key=settings.elevenlabs_api_key,
        elevenlabs_voice_id=ctx.elevenlabs_voice_id,
        supabase_url=settings.supabase_url,
        supabase_service_key=settings.supabase_service_key,
        supabase_bucket=settings.supabase_bucket,
        pushover_api_token=None,
        pushover_user_key=None,
    )

    # ------------------------------------------------------------------
    # Phase 2 — Fetch, score, select
    # ------------------------------------------------------------------
    openai_client = OpenAI(api_key=settings.openai_api_key)
    profile = ResearchProfile(
        focus_text=ctx.focus_text,
        embedding=ctx.embedding,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    papers = ArxivFetcher().fetch(ctx.arxiv_categories)
    if not papers:
        logger.info("No papers fetched for user %s.", user_id)
        return

    scored = PaperScorer(openai_client).score(papers, profile)

    # Filter seen before passing to selector (selector also checks, but we pass seen_ids directly)
    unseen_scored = [(p, s) for p, s in scored if p.arxiv_id not in seen_ids]
    if not unseen_scored:
        logger.info("All fetched papers already seen for user %s.", user_id)
        return

    # Use selector with an empty seen set (we already filtered above)
    config_no_seen = ResearchConfig(
        **{**config.__dict__, "output_dir": tmp_output}
    )

    selected = PaperSelector().select(unseen_scored, config_no_seen, top_n=5)
    if selected is None:
        # Nothing cleared the threshold — fall back to the highest scoring unseen paper
        top_paper, top_score = max(unseen_scored, key=lambda x: x[1])
        logger.info("No paper above threshold; falling back to top paper (score=%.4f).", top_score)
        import json as _json2
        from dataclasses import asdict
        _today = datetime.now().strftime("%Y%m%d")
        (tmp_output / f"selected_{_today}.json").write_text(
            _json2.dumps({**asdict(top_paper), "relevance_score": round(top_score, 6)}, indent=2),
            encoding="utf-8",
        )
        selected = top_paper

    # ------------------------------------------------------------------
    # Phase 3 — Brief generation
    # ------------------------------------------------------------------
    date_str = datetime.now().strftime("%Y%m%d")
    paper_path = tmp_output / f"selected_{date_str}.json"
    if not paper_path.exists():
        logger.error("selected_%s.json not written for user %s.", date_str, user_id)
        return

    import json as _json
    paper_data = _json.loads(paper_path.read_text(encoding="utf-8"))

    anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    generator = BriefGenerator(client=anthropic_client, model=settings.briefai_claude_model)
    brief_text, _ = generator.generate(
        paper=paper_data, focus_text=ctx.focus_text, output_dir=tmp_output
    )

    # ------------------------------------------------------------------
    # Phase 4a — TTS
    # ------------------------------------------------------------------
    mp3_bytes: bytes | None = None
    if settings.elevenlabs_api_key:
        from voice_agent.tts import TextToSpeech
        tts = TextToSpeech(api_key=settings.elevenlabs_api_key, voice_id=ctx.elevenlabs_voice_id)
        mp3_bytes, _ = tts.generate(brief_text=brief_text, output_dir=tmp_output)

    # ------------------------------------------------------------------
    # Phase 4b — Upload to Supabase Storage (per-user path)
    # ------------------------------------------------------------------
    storage_path: str | None = None
    audio_url: str | None = None

    if mp3_bytes:
        storage_path = f"{user_id}/brief_{date_str}.mp3"
        sb_storage = get_admin_client().storage.from_(settings.supabase_bucket)
        try:
            sb_storage.upload(storage_path, mp3_bytes, {"upsert": "true"})
            signed = sb_storage.create_signed_url(storage_path, 3600)
            audio_url = signed.get("signedURL") if isinstance(signed, dict) else None
        except Exception:
            logger.exception("Supabase upload failed for user %s.", user_id)

    # ------------------------------------------------------------------
    # Persist brief + seen paper to DB
    # ------------------------------------------------------------------
    sb.table("briefs").insert({
        "user_id": user_id,
        "arxiv_id": selected.arxiv_id,
        "title": selected.title,
        "authors": selected.authors,
        "relevance_score": round(paper_data.get("relevance_score", 0.0), 6),
        "brief_text": brief_text,
        "audio_url": audio_url,
        "storage_path": storage_path,
    }).execute()

    sb.table("seen_papers").upsert(
        {"user_id": user_id, "arxiv_id": selected.arxiv_id},
        on_conflict="user_id,arxiv_id",
    ).execute()

    logger.info("Brief generated for user %s: arXiv:%s", user_id, selected.arxiv_id)

    # ------------------------------------------------------------------
    # Phase 4c — Expo push notification
    # ------------------------------------------------------------------
    if ctx.expo_push_token and audio_url:
        _send_expo_push(
            token=ctx.expo_push_token,
            title=selected.title[:60],
            arxiv_id=selected.arxiv_id,
            audio_url=audio_url,
        )

    # Cleanup temp dir
    import shutil
    shutil.rmtree(tmp_output, ignore_errors=True)


def _send_expo_push(token: str, title: str, arxiv_id: str, audio_url: str) -> None:
    payload = json.dumps({
        "to": token,
        "title": title,
        "body": f"arXiv:{arxiv_id} — tap to listen to today's brief.",
        "data": {"audio_url": audio_url},
        "sound": "default",
    }).encode()

    req = urllib.request.Request(
        _EXPO_PUSH_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info("Expo push sent.")
    except urllib.error.URLError:
        logger.exception("Expo push failed.")
