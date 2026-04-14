#!/usr/bin/env python3
"""
BriefAI Research Ingestion — Phase 2 CLI.

Usage:
    python run_ingestion.py                  # Run daily ingestion
    python run_ingestion.py --setup-profile  # Create or update research profile
    python run_ingestion.py --top-n 10       # Show top 10 papers in summary
"""

from __future__ import annotations

import argparse
import sys

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="briefai-ingest",
        description="BriefAI Research Ingestion — fetch and score arXiv papers",
    )
    parser.add_argument(
        "--setup-profile",
        action="store_true",
        default=False,
        help="Create or update your research focus profile.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        metavar="N",
        help="Number of top papers to show in the terminal summary (default: 5).",
    )
    return parser.parse_args()


def setup_profile(config, openai_client: OpenAI) -> None:
    from research_agent.profile import ResearchProfile

    console.print(
        Panel(
            "[bold cyan]Research Profile Setup[/bold cyan]\n"
            "Describe your research focus in natural language.\n"
            "[dim]Example: I study transformer attention mechanism optimization "
            "targeting GPU/TPU hardware, focusing on memory bandwidth reduction "
            "and quantization-aware training.[/dim]",
            border_style="cyan",
        )
    )

    focus_text = Prompt.ask("\n[bold green]Your research focus[/bold green]").strip()
    if not focus_text:
        console.print("[red]Focus description cannot be empty.[/red]")
        sys.exit(1)

    example_abstracts: list[str] = []
    if Confirm.ask(
        "\nDo you want to provide example arXiv paper IDs to improve scoring accuracy?",
        default=False,
    ):
        console.print(
            "[dim]Enter up to 5 arXiv IDs (e.g. 2401.12345). Press Enter with no input to stop.[/dim]"
        )
        from research_agent.fetcher import ArxivFetcher
        import feedparser

        for i in range(5):
            arxiv_id = Prompt.ask(f"  Paper {i+1} arXiv ID (or Enter to skip)").strip()
            if not arxiv_id:
                break
            abstract = _fetch_abstract(arxiv_id)
            if abstract:
                example_abstracts.append(abstract)
                console.print(f"  [dim]✓ Fetched abstract for {arxiv_id}[/dim]")
            else:
                console.print(f"  [yellow]Could not fetch abstract for {arxiv_id} — skipping[/yellow]")

    with console.status("[dim]Embedding profile...[/dim]", spinner="dots"):
        if example_abstracts:
            profile = ResearchProfile.create_from_text_and_papers(
                focus_text, example_abstracts, openai_client
            )
        else:
            profile = ResearchProfile.create(focus_text, openai_client)

    path = profile.save(config.output_dir)
    console.print(f"\n[bold green]Profile saved to:[/bold green] {path}")


def run_ingestion(config, openai_client: OpenAI, top_n: int) -> None:
    from research_agent.profile import ResearchProfile
    from research_agent.fetcher import ArxivFetcher
    from research_agent.scorer import PaperScorer
    from research_agent.selector import PaperSelector

    if not ResearchProfile.exists(config.output_dir):
        console.print(
            "[red]No research profile found.[/red] "
            "Run: [bold]python run_ingestion.py --setup-profile[/bold]"
        )
        sys.exit(1)

    console.print(
        Panel(
            "[bold cyan]BriefAI Research Ingestion[/bold cyan]\n"
            f"Categories: {', '.join(config.arxiv_categories)}\n"
            f"Threshold: {config.relevance_threshold}",
            border_style="cyan",
        )
    )

    profile = ResearchProfile.load(config.output_dir)
    console.print(
        f"[dim]Profile loaded — focus: \"{profile.focus_text[:80]}...\"[/dim]\n"
    )

    fetcher = ArxivFetcher()
    papers = fetcher.fetch(config.arxiv_categories)

    if not papers:
        console.print("[yellow]No papers fetched. Check your network or arXiv RSS availability.[/yellow]")
        sys.exit(0)

    scorer = PaperScorer(openai_client)
    scored = scorer.score(papers, profile)

    selector = PaperSelector()
    selector.select(scored, config, top_n=top_n)


def _fetch_abstract(arxiv_id: str) -> str | None:
    """Fetch the abstract of a paper by arXiv ID using the arXiv API."""
    import urllib.request
    import xml.etree.ElementTree as ET

    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")
        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        summary = root.find(".//atom:entry/atom:summary", ns)
        return summary.text.strip() if summary is not None else None
    except Exception:
        return None


def main() -> None:
    args = parse_args()

    try:
        from research_agent.config import load_research_config, ConfigError
        config = load_research_config()
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)

    openai_client = OpenAI(api_key=config.openai_api_key)

    if args.setup_profile:
        setup_profile(config, openai_client)
    else:
        run_ingestion(config, openai_client, top_n=args.top_n)


if __name__ == "__main__":
    main()
