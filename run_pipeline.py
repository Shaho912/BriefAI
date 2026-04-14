#!/usr/bin/env python3
"""
BriefAI Full Pipeline — Phase 2 + Phase 3 in one command.

Runs: fetch arXiv → score papers → select top-1 → generate brief

Usage:
    python run_pipeline.py
    python run_pipeline.py --top-n 10
"""

from __future__ import annotations

import argparse
import sys

import anthropic
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="briefai-pipeline",
        description="BriefAI Full Pipeline — fetch, score, select, and brief in one run",
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
            "Phase 3: Generate Brief",
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

    import json
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    paper_path = config.output_dir / f"selected_{date_str}.json"
    paper = json.loads(paper_path.read_text(encoding="utf-8"))

    from brief_agent.generator import BriefGenerator
    anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    generator = BriefGenerator(client=anthropic_client, model=config.claude_model)
    generator.generate(paper=paper, focus_text=profile.focus_text, output_dir=config.output_dir)


if __name__ == "__main__":
    main()
