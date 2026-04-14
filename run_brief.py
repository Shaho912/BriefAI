#!/usr/bin/env python3
"""
BriefAI Brief Generation — Phase 3 CLI.

Usage:
    python run_brief.py                                      # Use today's selected paper
    python run_brief.py --date 20260414                      # Specific date
    python run_brief.py --paper output/selected_20260414.json  # Explicit file
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="briefai-brief",
        description="BriefAI Brief Generation — synthesize a research brief via Claude",
    )
    parser.add_argument(
        "--date",
        metavar="YYYYMMDD",
        default=None,
        help="Date of the selected paper to brief (default: today).",
    )
    parser.add_argument(
        "--paper",
        metavar="PATH",
        default=None,
        help="Explicit path to a selected_{date}.json file.",
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

    # Resolve selected paper path
    if args.paper:
        paper_path = Path(args.paper)
    else:
        date_str = args.date or datetime.now().strftime("%Y%m%d")
        paper_path = config.output_dir / f"selected_{date_str}.json"

    if not paper_path.exists():
        console.print(
            f"[red]Selected paper not found:[/red] {paper_path}\n"
            "Run [bold]python run_ingestion.py[/bold] first to fetch and select a paper."
        )
        sys.exit(1)

    paper = json.loads(paper_path.read_text(encoding="utf-8"))

    # Load research profile
    from research_agent.profile import ResearchProfile
    if not ResearchProfile.exists(config.output_dir):
        console.print(
            "[red]No research profile found.[/red] "
            "Run: [bold]python run_ingestion.py --setup-profile[/bold]"
        )
        sys.exit(1)

    profile = ResearchProfile.load(config.output_dir)

    console.print(
        Panel(
            f"[bold cyan]BriefAI Brief Generation[/bold cyan]\n"
            f"Paper: {paper.get('title', '')[:80]}\n"
            f"arXiv: {paper.get('arxiv_id', '')} | "
            f"Score: {paper.get('relevance_score', 0):.3f}",
            border_style="cyan",
        )
    )

    from brief_agent.generator import BriefGenerator

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    generator = BriefGenerator(client=client, model=config.claude_model)
    generator.generate(paper=paper, focus_text=profile.focus_text, output_dir=config.output_dir)


if __name__ == "__main__":
    main()
