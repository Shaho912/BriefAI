from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass
class Config:
    anthropic_api_key: str
    claude_model: str
    output_dir: Path


def load_config(
    output_dir: str | None = None,
    claude_model: str | None = None,
) -> Config:
    load_dotenv()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    resolved_output = Path(
        output_dir or os.getenv("BRIEFAI_OUTPUT_DIR", "./output")
    )

    return Config(
        anthropic_api_key=anthropic_key,
        claude_model=claude_model or os.getenv("BRIEFAI_CLAUDE_MODEL", "claude-sonnet-4-6"),
        output_dir=resolved_output,
    )
