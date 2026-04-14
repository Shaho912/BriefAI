#!/usr/bin/env python3
"""Quick test for Phase 4a — reads an existing brief and generates MP3 via ElevenLabs."""

import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console

console = Console()
load_dotenv()


def main() -> None:
    # Find the most recent brief file
    output_dir = Path("./output")
    briefs = sorted(output_dir.glob("brief_*.md"), reverse=True)

    if not briefs:
        console.print("[red]No brief files found in output/. Run python run_pipeline.py first.[/red]")
        sys.exit(1)

    brief_path = briefs[0]
    console.print(f"[dim]Using brief: {brief_path}[/dim]")
    brief_text = brief_path.read_text(encoding="utf-8")

    from research_agent.config import load_research_config, ConfigError
    try:
        config = load_research_config()
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    if not config.elevenlabs_api_key:
        console.print("[red]ELEVENLABS_API_KEY not set in .env[/red]")
        sys.exit(1)

    from voice_agent.tts import TextToSpeech
    tts = TextToSpeech(api_key=config.elevenlabs_api_key, voice_id=config.elevenlabs_voice_id)
    _, mp3_path = tts.generate(brief_text=brief_text, output_dir=output_dir)
    console.print(f"[bold green]Done! MP3 saved to: {mp3_path}[/bold green]")


if __name__ == "__main__":
    main()
