from __future__ import annotations

from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

from .config import Config
from .conversation import ConversationManager
from .prd_generator import PRDGenerator

console = Console()

BANNER = """\
[bold cyan]BriefAI Planning Agent[/bold cyan]
[dim]Powered by Claude + ara.so[/dim]

This tool will:
  [cyan]1.[/cyan] Ask you a few questions to understand your vision
  [cyan]2.[/cyan] Generate a production-grade PRD for BriefAI
"""


class PlanningAgent:
    """
    Top-level orchestrator for the BriefAI planning pipeline.

    Phase 1 — ConversationManager gathers requirements interactively.
    Phase 2 — PRDGenerator synthesizes the full PRD via Claude.
    """

    def __init__(
        self,
        config: Config,
        requirements_text: str | None = None,
    ) -> None:
        self.config = config
        self.requirements_text = requirements_text  # pre-loaded file bypass

        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.conversation = ConversationManager(self.client, config)
        self.generator = PRDGenerator(self.client, config)

    def run(self) -> Path:
        """
        Execute the full planning pipeline. Returns the path to the saved PRD.
        """
        console.print(Panel(BANNER, border_style="cyan", padding=(1, 4)))

        # ------------------------------------------------------------------
        # Phase 1 — Requirements gathering
        # ------------------------------------------------------------------
        if self.requirements_text:
            console.print(
                Panel(
                    "[bold cyan]Phase 1: Requirements[/bold cyan] (loaded from file)",
                    border_style="cyan",
                )
            )
            requirements_summary = self.requirements_text
        else:
            self.conversation.run()
            requirements_summary = self.conversation.extract_requirements_summary()

        # ------------------------------------------------------------------
        # Confirmation step — show summary, let user edit before Phase 2
        # ------------------------------------------------------------------
        console.print(Rule("[dim]Requirements Summary[/dim]"))
        console.print(requirements_summary)
        console.print(Rule())

        confirmed = Confirm.ask(
            "\nDoes this capture your vision correctly? Proceed to PRD generation?",
            default=True,
        )

        if not confirmed:
            extra = Prompt.ask(
                "Add any corrections or missing details "
                "(they will be appended to the summary)"
            ).strip()
            if extra:
                requirements_summary = requirements_summary + "\n\nAdditional context:\n" + extra

        # ------------------------------------------------------------------
        # Phase 2 — PRD generation
        # ------------------------------------------------------------------
        _, output_path = self.generator.generate(
            requirements_summary=requirements_summary,
            stream_to_terminal=True,
        )

        console.print(
            Panel(
                f"[bold green]Done![/bold green]\n\n"
                f"PRD saved to: [cyan]{output_path}[/cyan]\n\n"
                f"Next step: review the PRD and use it to guide BriefAI development.",
                border_style="green",
                padding=(1, 4),
            )
        )

        return output_path
