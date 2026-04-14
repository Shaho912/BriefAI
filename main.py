#!/usr/bin/env python3
"""
BriefAI Planning Agent — CLI entry point.

Usage:
    python main.py                            # Interactive mode (recommended)
    python main.py --skip-conversation \\
        --requirements-file reqs.txt          # Bypass Phase 1
    python main.py --model claude-opus-4-6    # Use a different Claude model
    python main.py --output-dir ./my-output   # Override output directory
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="briefai-planner",
        description="BriefAI Planning Agent — generates a PRD via Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        default=None,
        help="Directory where the PRD file is saved (default: ./output).",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Claude model to use (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "--skip-conversation",
        action="store_true",
        default=False,
        help="Skip Phase 1 interactive conversation. Requires --requirements-file.",
    )
    parser.add_argument(
        "--requirements-file",
        metavar="PATH",
        default=None,
        help="Path to a plain-text file containing pre-written requirements "
        "(used with --skip-conversation).",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=False,
        help="Do not stream PRD generation to the terminal (wait for full response).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.skip_conversation and not args.requirements_file:
        console.print(
            "[red]Error:[/red] --skip-conversation requires --requirements-file."
        )
        sys.exit(1)

    requirements_text: str | None = None
    if args.requirements_file:
        reqs_path = Path(args.requirements_file)
        if not reqs_path.exists():
            console.print(
                f"[red]Error:[/red] Requirements file not found: {reqs_path}"
            )
            sys.exit(1)
        requirements_text = reqs_path.read_text(encoding="utf-8").strip()
        if not requirements_text:
            console.print(
                f"[red]Error:[/red] Requirements file is empty: {reqs_path}"
            )
            sys.exit(1)

    try:
        from planning_agent.config import load_config, ConfigError
        config = load_config(
            output_dir=args.output_dir,
            claude_model=args.model,
        )
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)

    from planning_agent.agent import PlanningAgent

    agent = PlanningAgent(config=config, requirements_text=requirements_text)

    if args.no_stream:
        _original_generate = agent.generator.generate

        def _no_stream_generate(requirements_summary: str, **kwargs):
            return _original_generate(
                requirements_summary=requirements_summary,
                stream_to_terminal=False,
            )

        agent.generator.generate = _no_stream_generate

    try:
        agent.run()
        sys.exit(0)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted.[/yellow]")
        sys.exit(130)
    except Exception as exc:
        console.print(f"\n[red]Unexpected error:[/red] {exc}")
        raise


if __name__ == "__main__":
    main()
