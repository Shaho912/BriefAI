from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

PROFILE_FILENAME = "profile.json"


@dataclass
class ResearchProfile:
    focus_text: str
    embedding: list[float]   # text-embedding-3-small — 1536 dimensions
    created_at: str          # ISO 8601 timestamp

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, focus_text: str, openai_client: OpenAI) -> "ResearchProfile":
        """Embed the focus text and return a new profile."""
        embedding = _embed(focus_text, openai_client)
        return cls(
            focus_text=focus_text,
            embedding=embedding,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def create_from_text_and_papers(
        cls,
        focus_text: str,
        example_abstracts: list[str],
        openai_client: OpenAI,
    ) -> "ResearchProfile":
        """
        Create a profile by averaging the focus text embedding with embeddings
        of up to 5 example paper abstracts provided by the user during setup.
        """
        import numpy as np

        all_texts = [focus_text] + example_abstracts[:5]
        embeddings = [_embed(text, openai_client) for text in all_texts]
        avg_embedding = np.mean(embeddings, axis=0).tolist()

        return cls(
            focus_text=focus_text,
            embedding=avg_embedding,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / PROFILE_FILENAME
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, output_dir: Path) -> "ResearchProfile":
        path = output_dir / PROFILE_FILENAME
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    @classmethod
    def exists(cls, output_dir: Path) -> bool:
        return (output_dir / PROFILE_FILENAME).exists()


# ------------------------------------------------------------------
# Internal helper
# ------------------------------------------------------------------

def _embed(text: str, client: OpenAI) -> list[float]:
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return response.data[0].embedding
