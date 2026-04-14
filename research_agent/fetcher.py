from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
from rich.console import Console

console = Console()

ARXIV_RSS_BASE = "https://rss.arxiv.org/rss/{category}"
FETCH_DELAY_SECONDS = 1.0      # polite delay between category fetches
RECENCY_WINDOW_HOURS = 48      # arXiv RSS can lag; accept papers up to 48h old


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    categories: list[str]
    submitted_date: str        # ISO date string YYYY-MM-DD


class ArxivFetcher:
    """Fetches and deduplicates new papers from arXiv RSS feeds."""

    def fetch(self, categories: list[str]) -> list[Paper]:
        """
        Fetch papers from all given arXiv categories, deduplicate by arXiv ID,
        and return only papers submitted within the recency window.
        """
        seen_ids: set[str] = set()
        papers: list[Paper] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENCY_WINDOW_HOURS)

        for i, category in enumerate(categories):
            if i > 0:
                time.sleep(FETCH_DELAY_SECONDS)

            with console.status(
                f"[dim]Fetching arXiv {category}...[/dim]", spinner="dots"
            ):
                fetched = self._fetch_category(category, cutoff)

            new_papers = [p for p in fetched if p.arxiv_id not in seen_ids]
            seen_ids.update(p.arxiv_id for p in new_papers)
            papers.extend(new_papers)

            console.print(
                f"[dim]  {category}: {len(fetched)} entries, "
                f"{len(new_papers)} new after dedup[/dim]"
            )

        console.print(f"[bold]Fetched {len(papers)} papers total[/bold]")
        return papers

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_category(self, category: str, cutoff: datetime) -> list[Paper]:
        url = ARXIV_RSS_BASE.format(category=category)
        feed = feedparser.parse(url)

        papers = []
        for entry in feed.entries:
            paper = self._parse_entry(entry, category)
            if paper is None:
                continue
            # Filter by recency — skip if we can't determine date
            submitted = _parse_date(entry)
            if submitted and submitted < cutoff:
                continue
            papers.append(paper)

        return papers

    def _parse_entry(self, entry, category: str) -> Paper | None:
        try:
            arxiv_id = _extract_arxiv_id(entry.get("id", ""))
            if not arxiv_id:
                return None

            title = entry.get("title", "").replace("\n", " ").strip()
            abstract = entry.get("summary", "").replace("\n", " ").strip()
            url = entry.get("link", f"https://arxiv.org/abs/{arxiv_id}")

            # Authors: feedparser exposes as author_detail list or single author string
            authors = _extract_authors(entry)

            # Categories from arXiv tags
            tags = entry.get("tags", [])
            categories = [t.get("term", "") for t in tags if t.get("term")]
            if not categories:
                categories = [category]

            submitted_date = _parse_date(entry)
            date_str = submitted_date.strftime("%Y-%m-%d") if submitted_date else ""

            return Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                url=url,
                categories=categories,
                submitted_date=date_str,
            )
        except Exception:
            return None


# ------------------------------------------------------------------
# Parsing utilities
# ------------------------------------------------------------------

def _extract_arxiv_id(raw_id: str) -> str:
    """Extract clean arXiv ID from a URL or raw string like 'oai:arXiv.org:2401.12345'."""
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", raw_id)
    return match.group(1) if match else ""


def _extract_authors(entry) -> list[str]:
    if hasattr(entry, "authors") and entry.authors:
        return [a.get("name", "") for a in entry.authors if a.get("name")]
    if hasattr(entry, "author") and entry.author:
        return [entry.author]
    return []


def _parse_date(entry) -> datetime | None:
    """Parse submission date from feedparser entry. Returns UTC datetime or None."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None
