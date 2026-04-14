#!/usr/bin/env python3
"""
BriefAI Full Pipeline — Phases 2, 3, and 4 in one command.

Runs: fetch arXiv → score → select → generate brief → TTS → upload → notify

Usage:
    python run_pipeline.py
    python run_pipeline.py --top-n 10
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

import anthropic
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="briefai-pipeline",
        description="BriefAI Full Pipeline — fetch, score, select, brief, and deliver",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        metavar="N",
        help="Number of top papers to show in the scoring summary (default: 5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from research_agent.config import load_research_config, ConfigError
        config = load_research_config()
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)

    from research_agent.profile import ResearchProfile
    if not ResearchProfile.exists(config.output_dir):
        console.print(
            "[red]No research profile found.[/red] "
            "Run: [bold]python run_ingestion.py --setup-profile[/bold]"
        )
        sys.exit(1)

    console.print(
        Panel(
            "[bold cyan]BriefAI Full Pipeline[/bold cyan]\n"
            "Phase 2: Fetch → Score → Select\n"
            "Phase 3: Generate Brief\n"
            "Phase 4: Voice → Upload → Notify",
            border_style="cyan",
        )
    )

    # ------------------------------------------------------------------
    # Phase 2 — Ingestion
    # ------------------------------------------------------------------
    console.print(Rule("[dim]Phase 2: Research Ingestion[/dim]"))

    openai_client = OpenAI(api_key=config.openai_api_key)
    profile = ResearchProfile.load(config.output_dir)

    from research_agent.fetcher import ArxivFetcher
    from research_agent.scorer import PaperScorer
    from research_agent.selector import PaperSelector

    papers = ArxivFetcher().fetch(config.arxiv_categories)
    if not papers:
        console.print("[yellow]No papers fetched. Exiting.[/yellow]")
        sys.exit(0)

    scored = PaperScorer(openai_client).score(papers, profile)
    selected = PaperSelector().select(scored, config, top_n=args.top_n)

    if selected is None:
        console.print("[yellow]No paper selected. Skipping brief generation.[/yellow]")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Phase 3 — Brief generation
    # ------------------------------------------------------------------
    console.print(Rule("[dim]Phase 3: Brief Generation[/dim]"))

    date_str = datetime.now().strftime("%Y%m%d")
    paper_path = config.output_dir / f"selected_{date_str}.json"
    paper = json.loads(paper_path.read_text(encoding="utf-8"))

    from brief_agent.generator import BriefGenerator
    anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    generator = BriefGenerator(client=anthropic_client, model=config.claude_model)
    brief_text, _ = generator.generate(
        paper=paper, focus_text=profile.focus_text, output_dir=config.output_dir
    )

    # ------------------------------------------------------------------
    # Phase 4a — Voice generation (ElevenLabs)
    # ------------------------------------------------------------------
    console.print(Rule("[dim]Phase 4: Voice, Upload & Notify[/dim]"))

    mp3_bytes: bytes | None = None
    audio_url: str | None = None

    if config.elevenlabs_api_key:
        from voice_agent.tts import TextToSpeech
        tts = TextToSpeech(
            api_key=config.elevenlabs_api_key,
            voice_id=config.elevenlabs_voice_id,
        )
        mp3_bytes, _ = tts.generate(brief_text=brief_text, output_dir=config.output_dir)
    else:
        console.print("[dim]ELEVENLABS_API_KEY not set — skipping audio generation.[/dim]")

    # ------------------------------------------------------------------
    # Phase 4b — Upload to Supabase Storage
    # ------------------------------------------------------------------
    if mp3_bytes and config.supabase_url and config.supabase_service_key:
        from delivery_agent.storage import SupabaseStorage
        storage = SupabaseStorage(
            url=config.supabase_url,
            service_key=config.supabase_service_key,
            bucket=config.supabase_bucket,
        )
        filename = f"brief_{date_str}.mp3"
        audio_url = storage.upload(mp3_bytes=mp3_bytes, filename=filename)
    else:
        if mp3_bytes:
            console.print("[dim]SUPABASE_URL not set — skipping upload.[/dim]")

    # ------------------------------------------------------------------
    # Phase 4c — Push notification via ntfy.sh
    # ------------------------------------------------------------------
    if audio_url and config.pushover_api_token and config.pushover_user_key:
        from delivery_agent.notifier import PushoverNotifier
        PushoverNotifier(
            api_token=config.pushover_api_token,
            user_key=config.pushover_user_key,
        ).send(
            paper_title=paper.get("title", ""),
            audio_url=audio_url,
            arxiv_id=paper.get("arxiv_id", ""),
            relevance_score=paper.get("relevance_score", 0.0),
        )
    else:
        if not config.pushover_api_token or not config.pushover_user_key:
            console.print("[dim]PUSHOVER credentials not set — skipping push notification.[/dim]")
        elif not audio_url:
            console.print("[dim]No audio URL available — skipping push notification.[/dim]")

    console.print(
        Panel(
            "[bold green]Pipeline complete![/bold green]\n\n"
            + (f"Audio: {audio_url}" if audio_url else "Audio: saved locally only"),
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
