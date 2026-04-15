from __future__ import annotations

"""
Onboarding chat manager — adapted from planning_agent/conversation.py.

Key differences from the CLI version:
- No rich/terminal output — runs inside a FastAPI request context
- User input comes from HTTP request bodies, not Prompt.ask()
- _stream_response() is an async generator that yields SSE text chunks
- self.messages is persisted to onboarding_sessions.messages (jsonb) after every turn
"""

from typing import AsyncGenerator

import anthropic

SENTINEL = "REQUIREMENTS_COMPLETE"
MAX_TURNS = 12
WRAP_UP_AT_TURN = 10

ONBOARDING_FACILITATOR_PROMPT = """\
You are a friendly research concierge helping a user set up their BriefAI profile.

BriefAI delivers a daily audio brief about the most relevant new research paper in \
the user's field. Your job is to understand what they care about so we can \
automatically surface the right papers each morning.

Ask targeted questions ONE AT A TIME to understand:
1. Their research domain or professional field
2. Specific topics or sub-fields they care most about (e.g. "transformer efficiency", \
   "hardware acceleration for ML inference")
3. How they'd describe a "perfect" paper discovery — what makes a paper exciting to them
4. Whether there are adjacent fields they occasionally care about

Rules:
- Ask ONE question per turn. Be conversational and warm, not formal.
- Do NOT ask about delivery preferences or technical setup — that is handled separately.
- When you have a clear picture of their research focus (usually 4–6 turns), \
  respond with the exact string: REQUIREMENTS_COMPLETE
"""

REQUIREMENTS_EXTRACTION_PROMPT = """\
You are a precise technical writer. Summarize the following research-focus conversation \
into a dense, specific paragraph of 100–200 words describing what this person studies \
and finds interesting.

Preserve concrete details: specific sub-fields, techniques, application areas, \
types of papers they find exciting. Write it as a profile description, not a summary \
of the conversation.

Do not add anything not mentioned in the conversation.

Conversation:
{conversation_text}
"""


class OnboardingChat:
    """
    Manages the multi-turn onboarding conversation.
    State (self.messages) is loaded from and saved to Supabase on every turn.
    """

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        session_id: str,
        messages: list[dict],
    ) -> None:
        self.client = client
        self.model = model
        self.session_id = session_id
        self.messages: list[dict] = messages  # pre-loaded from DB

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.messages if m["role"] == "user")

    async def send_message(self, user_content: str) -> AsyncGenerator[str, None]:
        """
        Accept one user message and yield Claude's reply as SSE text chunks.
        Caller is responsible for persisting self.messages to DB after iteration completes.
        """
        # Add wrap-up nudge near the end
        content = user_content
        if self.turn_count >= WRAP_UP_AT_TURN:
            content = (
                user_content
                + "\n\n[System note: Please wrap up now and respond with "
                "REQUIREMENTS_COMPLETE if you have enough information.]"
            )

        self.messages.append({"role": "user", "content": content})
        self._apply_cache_breakpoint()

        full_text = ""
        async for chunk in self._stream_response_sse():
            full_text += chunk
            yield chunk

        self.messages.append({"role": "assistant", "content": full_text})

    async def opening_message(self) -> AsyncGenerator[str, None]:
        """
        Generate Claude's first message (no user input yet).
        Caller is responsible for persisting self.messages to DB after iteration completes.
        """
        full_text = ""
        async for chunk in self._stream_response_sse():
            full_text += chunk
            yield chunk

        self.messages.append({"role": "assistant", "content": full_text})

    def extract_requirements_summary(self) -> str:
        """
        Collapse the conversation into a dense focus-text description.
        Used by POST /onboarding/session/{id}/complete to build the embedding.
        """
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in self.messages
            if isinstance(m.get("content"), str)
        )
        response = self.client.messages.create(
            model=self.model,
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

    def is_complete(self) -> bool:
        """Returns True if Claude has signalled REQUIREMENTS_COMPLETE."""
        for msg in self.messages:
            if msg["role"] == "assistant" and SENTINEL in str(msg.get("content", "")):
                return True
        return False

    # ------------------------------------------------------------------
    # Private helpers (ported unchanged from ConversationManager)
    # ------------------------------------------------------------------

    async def _stream_response_sse(self) -> AsyncGenerator[str, None]:
        system = [
            {
                "type": "text",
                "text": ONBOARDING_FACILITATOR_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        seed_messages = self.messages if self.messages else [
            {"role": "user", "content": "Please begin by introducing yourself and asking the first question."}
        ]

        with self.client.messages.stream(
            model=self.model,
            max_tokens=512,
            system=system,
            messages=seed_messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _apply_cache_breakpoint(self) -> None:
        """Moving cache breakpoint — identical logic to planning_agent/conversation.py."""
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
