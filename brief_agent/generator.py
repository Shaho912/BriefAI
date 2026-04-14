from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.rule import Rule

from .prompts import BRIEF_SYSTEM_PROMPT, BRIEF_USER_TEMPLATE

console = Console()

# Strips the arXiv RSS feed prefix that appears in fetched abstracts:
# "arXiv:2604.09791v1 Announce Type: cross  Abstract: ..."
_ARXIV_PREFIX_RE = re.compile(
    r"^arXiv:\S+\s+Announce\s+Type:\s+\S+\s+Abstract:\s*",
    re.IGNORECASE,
)


class BriefGenerator:
    """
    Phase 3: generates the 4-part research brief via a single cached Claude call.
    """

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def generate(
        self,
        paper: dict,
        focus_text: str,
        output_dir: Path,
    ) -> tuple[str, Path]:
        """
        Generate the brief for a selected paper and save it to output_dir.

        Args:
            paper: dict loaded from selected_{date}.json
            focus_text: user's research focus from profile.json
            output_dir: where to save brief_{date}.md

        Returns:
            (brief_text, output_path)
        """
        abstract = _clean_abstract(paper.get("abstract", ""))

        user_message = BRIEF_USER_TEMPLATE.format(
            focus_text=focus_text,
            title=paper.get("title", ""),
            authors=", ".join(paper.get("authors", [])),
            abstract=abstract,
            arxiv_id=paper.get("arxiv_id", ""),
            url=paper.get("url", ""),
            submitted_date=paper.get("submitted_date", ""),
            relevance_score=paper.get("relevance_score", 0.0),
        )

        brief_text = self._call_claude(user_message)
        output_path = self._save(brief_text, paper, output_dir)

        console.print(f"\n[bold green]Brief saved to:[/bold green] {output_path}")
        return brief_text, output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_claude(self, user_message: str) -> str:
        system = [
            {
                "type": "text",
                "text": BRIEF_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        console.print(Rule("[dim]Daily Research Brief[/dim]"))

        full_text = ""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", highlight=False)
                full_text += text

            final = stream.get_final_message()
            self._print_usage(final.usage)

        console.print(Rule())
        return full_text

    def _save(self, brief_text: str, paper: dict, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")

        # Prepend a metadata header for traceability
        header = (
            f"---\n"
            f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"arxiv_id: {paper.get('arxiv_id', '')}\n"
            f"title: {paper.get('title', '')}\n"
            f"relevance_score: {paper.get('relevance_score', 0.0):.3f}\n"
            f"---\n\n"
        )

        output_path = output_dir / f"brief_{date_str}.md"
        output_path.write_text(header + brief_text, encoding="utf-8")
        return output_path

    def _print_usage(self, usage) -> None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
        console.print(
            f"\n[dim]Tokens — input: {usage.input_tokens} | "
            f"output: {usage.output_tokens} | "
            f"cache created: {cache_created} | "
            f"cache read: {cache_read}[/dim]"
        )


def _clean_abstract(abstract: str) -> str:
    """Strip the arXiv RSS feed prefix from abstracts."""
    return _ARXIV_PREFIX_RE.sub("", abstract).strip()
