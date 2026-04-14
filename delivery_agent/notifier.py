from __future__ import annotations

import json
import urllib.request

from rich.console import Console

console = Console()

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


class PushoverNotifier:
    """Sends a push notification via Pushover with a link to the audio brief."""

    def __init__(self, api_token: str, user_key: str) -> None:
        self.api_token = api_token
        self.user_key = user_key

    def send(
        self,
        paper_title: str,
        audio_url: str,
        arxiv_id: str,
        relevance_score: float,
    ) -> None:
        """POST a notification to Pushover with a direct link to the audio."""
        title = paper_title[:100]
        message = (
            f"Relevance: {relevance_score:.2f} | arXiv:{arxiv_id}\n\n"
            f"Tap the link to listen to today's research brief."
        )

        payload = json.dumps({
            "token": self.api_token,
            "user": self.user_key,
            "title": title,
            "message": message,
            "url": audio_url,
            "url_title": "Listen to Brief",
            "priority": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            PUSHOVER_API_URL,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with console.status("[dim]Sending push notification via Pushover...[/dim]", spinner="dots"):
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status

        if status == 200:
            console.print("[bold green]Push notification sent via Pushover.[/bold green]")
        else:
            console.print(f"[yellow]Pushover returned status {status}[/yellow]")
