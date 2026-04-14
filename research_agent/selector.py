from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import ResearchConfig
from .fetcher import Paper

console = Console()

FALLBACK_THRESHOLD = 0.60
SEEN_PAPERS_FILENAME = "seen_papers.json"


class PaperSelector:
    """
    Applies relevance threshold logic, saves output JSON files,
    and prints a terminal summary of the top scored papers.
    """

    def select(
        self,
        scored_papers: list[tuple[Paper, float]],
        config: ResearchConfig,
        top_n: int = 5,
    ) -> Paper | None:
        """
        Select the top-1 unseen paper above the relevance threshold.

        Saves:
          output/candidates_{YYYYMMDD}.json  — full scored list
          output/selected_{YYYYMMDD}.json    — top-1 paper + score
          output/seen_papers.json            — running list of briefed arXiv IDs

        Returns the selected Paper or None if no paper qualifies.
        """
        if not scored_papers:
            console.print("[yellow]No papers fetched — nothing to select.[/yellow]")
            return None

        today = datetime.now().strftime("%Y%m%d")
        config.output_dir.mkdir(parents=True, exist_ok=True)

        # Save full candidate list regardless of threshold
        self._save_candidates(scored_papers, config.output_dir, today)

        # Filter out already-briefed papers
        seen_ids = self._load_seen(config.output_dir)
        unseen_papers = [(p, s) for p, s in scored_papers if p.arxiv_id not in seen_ids]
        if len(unseen_papers) < len(scored_papers):
            skipped = len(scored_papers) - len(unseen_papers)
            console.print(f"[dim]Skipping {skipped} already-briefed paper(s).[/dim]")

        # Apply threshold — with fallback
        qualifying = [
            (p, s) for p, s in unseen_papers if s >= config.relevance_threshold
        ]

        if not qualifying:
            console.print(
                f"[yellow]No unseen papers above threshold {config.relevance_threshold:.2f}. "
                f"Trying fallback threshold {FALLBACK_THRESHOLD:.2f}...[/yellow]"
            )
            qualifying = [
                (p, s) for p, s in unseen_papers if s >= FALLBACK_THRESHOLD
            ]

        if not qualifying:
            console.print(
                "[yellow]No qualifying unseen papers today. "
                "Consider lowering RELEVANCE_THRESHOLD in .env.[/yellow]"
            )
            self._print_top_n(scored_papers, top_n)
            return None

        top_paper, top_score = qualifying[0]

        # Save selected paper and record it as seen
        self._save_selected(top_paper, top_score, config.output_dir, today)
        self._mark_seen(top_paper.arxiv_id, config.output_dir)

        # Print terminal summary
        self._print_top_n(scored_papers, top_n)

        console.print(
            f"\n[bold green]Selected:[/bold green] {top_paper.title[:80]}\n"
            f"[dim]arXiv:{top_paper.arxiv_id} | score: {top_score:.4f}[/dim]"
        )

        return top_paper

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save_candidates(
        self,
        scored_papers: list[tuple[Paper, float]],
        output_dir: Path,
        today: str,
    ) -> None:
        candidates = [
            {**asdict(paper), "relevance_score": round(score, 6)}
            for paper, score in scored_papers
        ]
        path = output_dir / f"candidates_{today}.json"
        path.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
        console.print(f"[dim]Candidates saved to {path}[/dim]")

    def _save_selected(
        self,
        paper: Paper,
        score: float,
        output_dir: Path,
        today: str,
    ) -> None:
        data = {**asdict(paper), "relevance_score": round(score, 6)}
        path = output_dir / f"selected_{today}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[dim]Selected paper saved to {path}[/dim]")

    def _load_seen(self, output_dir: Path) -> set[str]:
        path = output_dir / SEEN_PAPERS_FILENAME
        if not path.exists():
            return set()
        return set(json.loads(path.read_text(encoding="utf-8")))

    def _mark_seen(self, arxiv_id: str, output_dir: Path) -> None:
        seen = self._load_seen(output_dir)
        seen.add(arxiv_id)
        path = output_dir / SEEN_PAPERS_FILENAME
        path.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")

    def _print_top_n(
        self,
        scored_papers: list[tuple[Paper, float]],
        top_n: int,
    ) -> None:
        table = Table(title=f"Top {min(top_n, len(scored_papers))} Papers by Relevance")
        table.add_column("Score", style="cyan", width=7)
        table.add_column("arXiv ID", style="dim", width=14)
        table.add_column("Title", no_wrap=False)

        for paper, score in scored_papers[:top_n]:
            title = paper.title if len(paper.title) <= 80 else paper.title[:77] + "..."
            table.add_row(f"{score:.4f}", paper.arxiv_id, title)

        console.print(table)
