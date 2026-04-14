from __future__ import annotations

import anthropic
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .config import Config
from .prompts import CONVERSATION_FACILITATOR_PROMPT, REQUIREMENTS_EXTRACTION_PROMPT

console = Console()

SENTINEL = "REQUIREMENTS_COMPLETE"
MAX_TURNS = 12
WRAP_UP_AT_TURN = 10


class ConversationManager:
    """
    Manages the Phase 1 multi-turn requirements-gathering conversation.

    Uses prompt caching on the system prompt (5-min TTL) and applies a
    moving cache breakpoint to the conversation history on every turn so
    that prior exchanges are served from cache rather than re-processed.
    """

    def __init__(self, client: anthropic.Anthropic, config: Config) -> None:
        self.client = client
        self.config = config
        self.messages: list[dict] = []

    def run(self) -> list[dict]:
        """
        Run the interactive conversation loop.
        Returns the full messages list for handoff to the PRD generator.
        """
        console.print(
            Panel(
                "[bold cyan]Phase 1: Requirements Gathering[/bold cyan]\n"
                "I'll ask you a few questions to understand your vision for BriefAI.\n"
                "[dim]Press Ctrl+C at any time to stop and proceed with what was gathered.[/dim]",
                border_style="cyan",
            )
        )

        try:
            # Kick off with an opening question from Claude
            response = self._stream_response()
            self.messages.append({"role": "assistant", "content": response})

            if SENTINEL in response:
                return self.messages

            turn = 1
            while turn < MAX_TURNS:
                user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
                if not user_input:
                    continue

                self.messages.append({"role": "user", "content": user_input})

                # Apply moving cache breakpoint to the second-to-last message
                self._apply_cache_breakpoint()

                # At turn WRAP_UP_AT_TURN, nudge Claude to finish
                if turn >= WRAP_UP_AT_TURN:
                    self.messages[-1]["content"] = (
                        user_input
                        + "\n\n[System note: Please wrap up the conversation now "
                        "and respond with REQUIREMENTS_COMPLETE if you have enough info.]"
                    )

                response = self._stream_response()
                self.messages.append({"role": "assistant", "content": response})

                if SENTINEL in response:
                    console.print("\n[bold cyan]Requirements captured.[/bold cyan]")
                    break

                turn += 1

        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Conversation interrupted.[/yellow]"
            )
            if not self.messages:
                raise
            console.print("[dim]Proceeding with requirements gathered so far.[/dim]")

        return self.messages

    def extract_requirements_summary(self) -> str:
        """
        Collapse the conversation into a clean structured summary via a
        small, non-cached Claude call. Returns a 200-350 word paragraph.
        """
        if not self.messages:
            return ""

        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in self.messages
            if isinstance(m.get("content"), str)
        )

        with console.status("[dim]Summarizing requirements...[/dim]", spinner="dots"):
            response = self.client.messages.create(
                model=self.config.claude_model,
                max_tokens=512,
                messages=[
                    {
                        "role": "user",
                        "content": REQUIREMENTS_EXTRACTION_PROMPT.format(
                            conversation_text=conversation_text
                        ),
                    }
                ],
            )

        return response.content[0].text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _stream_response(self) -> str:
        """
        Call Claude with streaming, print the response to the terminal,
        and return the full text.
        """
        system = [
            {
                "type": "text",
                "text": CONVERSATION_FACILITATOR_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        console.print("\n[bold blue]BriefAI[/bold blue] ", end="")

        full_text = ""
        with self.client.messages.stream(
            model=self.config.claude_model,
            max_tokens=512,
            system=system,
            messages=self.messages if self.messages else [
                {"role": "user", "content": "Please begin the requirements gathering."}
            ],
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", highlight=False)
                full_text += text

        console.print()  # newline after streamed response
        return full_text

    def _apply_cache_breakpoint(self) -> None:
        """
        Apply cache_control to the second-to-last user message so that all
        prior conversation is cached on the next API call (moving breakpoint).

        Strips cache_control from all messages first to avoid exceeding the
        Anthropic limit of 4 cache_control blocks per request (1 is used by
        the system prompt, leaving 3 for conversation — but we only need 1).
        """
        # Remove all existing cache_control blocks from every message
        for msg in self.messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)

        user_messages = [
            (i, m) for i, m in enumerate(self.messages) if m["role"] == "user"
        ]
        if len(user_messages) < 2:
            return

        # Apply to second-to-last user message (most recent fully exchanged turn)
        idx, msg = user_messages[-2]
        content = msg["content"]
        if isinstance(content, str):
            self.messages[idx]["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        elif isinstance(content, list) and content:
            last_block = content[-1]
            if isinstance(last_block, dict):
                last_block["cache_control"] = {"type": "ephemeral"}
