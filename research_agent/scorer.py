from __future__ import annotations

import numpy as np
from openai import OpenAI
from rich.console import Console

from .fetcher import Paper
from .profile import ResearchProfile

console = Console()

BATCH_SIZE = 100   # OpenAI embedding API batch limit


class PaperScorer:
    """
    Scores papers against a research profile using OpenAI embeddings
    and cosine similarity.
    """

    def __init__(self, openai_client: OpenAI) -> None:
        self.client = openai_client

    def score(
        self,
        papers: list[Paper],
        profile: ResearchProfile,
    ) -> list[tuple[Paper, float]]:
        """
        Embed all paper abstracts and compute cosine similarity against the
        profile embedding. Returns (paper, score) tuples sorted descending.
        """
        if not papers:
            return []

        profile_vec = np.array(profile.embedding, dtype=np.float32)

        with console.status(
            f"[dim]Scoring {len(papers)} papers...[/dim]", spinner="dots"
        ):
            abstract_embeddings = self._embed_batch(
                [p.abstract for p in papers]
            )

        scored = []
        for paper, embedding in zip(papers, abstract_embeddings):
            paper_vec = np.array(embedding, dtype=np.float32)
            score = float(_cosine_similarity(profile_vec, paper_vec))
            scored.append((paper, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches of BATCH_SIZE. Returns list of embedding vectors."""
        embeddings: list[list[float]] = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            response = self.client.embeddings.create(
                input=batch,
                model="text-embedding-3-small",
            )
            # Preserve order — OpenAI returns embeddings in the same order as input
            batch_embeddings = [d.embedding for d in sorted(response.data, key=lambda x: x.index)]
            embeddings.extend(batch_embeddings)

        return embeddings


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
