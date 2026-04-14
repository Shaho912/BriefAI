from __future__ import annotations

from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from .config import Config
from .prompts import PRD_GENERATION_PROMPT, PRD_USER_MESSAGE_TEMPLATE

console = Console()


class PRDGenerator:
    """
    Phase 2: generates the full PRD via a single cached Claude call.

    The long system prompt is cached with ephemeral cache_control so it is
    reused across multiple runs within the same session without re-processing.
    """

    def __init__(self, client: anthropic.Anthropic, config: Config) -> None:
        self.client = client
        self.config = config

    def generate(
        self,
        requirements_summary: str,
        stream_to_terminal: bool = True,
    ) -> tuple[str, Path]:
        """
        Generate the PRD and save it to a timestamped file.

        Returns (prd_text, output_path).
        """
        console.print(
            Panel(
                "[bold cyan]Phase 2: PRD Generation[/bold cyan]\n"
                "Generating your Product Requirements Document...",
                border_style="cyan",
            )
        )

        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = PRD_GENERATION_PROMPT.replace("{today}", today)

        user_message = PRD_USER_MESSAGE_TEMPLATE.format(
            requirements_summary=requirements_summary,
            today=today,
        )

        prd_text = self._call_claude(system_prompt, user_message, stream_to_terminal)
        output_path = self._write_to_file(prd_text)

        console.print(f"\n[bold green]PRD saved to:[/bold green] {output_path}")
        return prd_text, output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        stream_to_terminal: bool,
    ) -> str:
        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        messages = [{"role": "user", "content": user_message}]

        if stream_to_terminal:
            return self._stream_to_terminal(system, messages)
        else:
            return self._blocking_call(system, messages)

    def _stream_to_terminal(self, system: list, messages: list) -> str:
        console.print(Rule("[dim]PRD Preview[/dim]"))
        full_text = ""

        with self.client.messages.stream(
            model=self.config.claude_model,
            max_tokens=8192,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", highlight=False)
                full_text += text

            # Print cache usage stats after stream completes
            final_msg = stream.get_final_message()
            self._print_usage_stats(final_msg.usage)

        console.print(Rule())
        return full_text

    def _blocking_call(self, system: list, messages: list) -> str:
        with console.status("[dim]Generating PRD...[/dim]", spinner="dots"):
            response = self.client.messages.create(
                model=self.config.claude_model,
                max_tokens=8192,
                system=system,
                messages=messages,
            )
        self._print_usage_stats(response.usage)
        return response.content[0].text

    def _write_to_file(self, prd_text: str) -> Path:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.config.output_dir / f"BriefAI_PRD_{timestamp}.md"
        output_path.write_text(prd_text, encoding="utf-8")
        return output_path

    def _print_usage_stats(self, usage) -> None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0

        console.print(
            f"\n[dim]Token usage — "
            f"input: {input_tokens} | "
            f"output: {output_tokens} | "
            f"cache created: {cache_created} | "
            f"cache read: {cache_read}[/dim]"
        )
