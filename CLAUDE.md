# BriefAI

Researchers and professionals waste hours manually scanning papers, feeds, and newsletters to stay current in their domain. BriefAI solves this by running an AI agent that ingests research from the web daily, synthesizes it into a concise brief, and delivers it as a voice summary — so users get a knowledgeable peer-style update without the noise.

**PRD:** [output/BriefAI_PRD_20260414_011211.md](output/BriefAI_PRD_20260414_011211.md)

## Tech Stack

- **Claude API (Anthropic)** — LLM backbone for requirements gathering, research synthesis, and brief generation
- **ara.so** — agent runtime for browser automation, scheduling daily triggers, and persistent memory (Phase 4)
- **ElevenLabs** — text-to-speech for voice delivery of the daily brief (Phase 4)
- **Python 3.13+** with `anthropic`, `rich`, `python-dotenv`

---

## Environment

Required in `.env` (see `.env.example`):
- `ANTHROPIC_API_KEY` — get from console.anthropic.com

Install and run:
```bash
pip install -r requirements.txt --no-warn-script-location
python main.py
```

## Architectural Decisions

- All Claude prompts live in `planning_agent/prompts.py` — never hardcode prompts elsewhere
- ElevenLabs and ara.so are intentionally absent until Phase 4 — do not add them to earlier phases
- Use `rich.console.Console` for all terminal output instead of `print()`

## Gotchas

- Anthropic API allows max 4 `cache_control` blocks per request — always strip existing ones from message history before applying a new cache breakpoint or the API returns a 400
- Always use prompt caching (`cache_control: ephemeral`) on system prompts — skipping it wastes tokens on every turn

## Code Style

- Python 3.13+
- Max line length: 100 characters
- Error messages lead with the cause: `"ANTHROPIC_API_KEY is not set."` not `"Error: missing key"`
