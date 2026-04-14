from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from elevenlabs.client import ElevenLabs
from rich.console import Console

console = Console()

# Maps markdown section headers to natural spoken transitions
_HEADER_MAP = {
    "## Why This Matters To You": "Why this matters to you.",
    "## What They Did": "What they did.",
    "## The Breakdown": "The breakdown.",
    "## Citation": "Citation.",
}


class TextToSpeech:
    """Converts a brief markdown file to MP3 audio via ElevenLabs."""

    def __init__(self, api_key: str, voice_id: str) -> None:
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id

    def generate(self, brief_text: str, output_dir: Path) -> tuple[bytes, Path]:
        """
        Strip markdown formatting, generate MP3 via ElevenLabs, save locally.

        Returns (mp3_bytes, output_path).
        """
        spoken_text = _markdown_to_speech(brief_text)

        with console.status("[dim]Generating audio via ElevenLabs...[/dim]", spinner="dots"):
            audio_chunks = self.client.text_to_speech.convert(
                text=spoken_text,
                voice_id=self.voice_id,
                model_id="eleven_multilingual_v2",
                voice_settings={
                    "stability": 0.75,
                    "similarity_boost": 0.60,
                },
            )
            mp3_bytes = b"".join(audio_chunks)

        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        output_path = output_dir / f"brief_{date_str}.mp3"
        output_path.write_bytes(mp3_bytes)

        console.print(f"[bold green]Audio saved to:[/bold green] {output_path}")
        return mp3_bytes, output_path


def _markdown_to_speech(text: str) -> str:
    """
    Convert brief markdown to clean spoken text:
    - Replace section headers with natural transitions
    - Strip bold markers (**text**)
    - Strip horizontal rules (---)
    - Strip YAML front matter (--- ... ---)
    - Collapse multiple blank lines
    """
    # Strip YAML front matter block at top of file
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)

    # Replace known section headers with spoken transitions
    for md_header, spoken in _HEADER_MAP.items():
        text = text.replace(md_header, spoken)

    # Strip any remaining ## headers
    text = re.sub(r"^##+ .+$", "", text, flags=re.MULTILINE)

    # Strip bold markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)

    # Strip horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)

    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
