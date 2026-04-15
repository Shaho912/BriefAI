from __future__ import annotations

import anthropic
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ..config import settings
from ..dependencies import CurrentUser
from ..models import MessageRequest, SessionCreated, SessionDetail
from ..pipeline.onboarding_chat import OnboardingChat
from ..supabase_client import get_admin_client

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _get_chat(session_id: str, user_id: str) -> tuple[OnboardingChat, dict]:
    """Load an onboarding session from DB and return (chat, row)."""
    sb = get_admin_client()
    row = (
        sb.table("onboarding_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    chat = OnboardingChat(
        client=client,
        model=settings.briefai_claude_model,
        session_id=session_id,
        messages=row.data.get("messages", []),
    )
    return chat, row.data


def _save_messages(session_id: str, messages: list[dict], status_str: str = "in_progress") -> None:
    sb = get_admin_client()
    sb.table("onboarding_sessions").update(
        {"messages": messages, "status": status_str}
    ).eq("id", session_id).execute()


@router.post("/session", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(user_id: CurrentUser) -> SessionCreated:
    sb = get_admin_client()
    result = sb.table("onboarding_sessions").insert(
        {"user_id": user_id, "messages": [], "status": "in_progress"}
    ).execute()
    session_id = result.data[0]["id"]
    return SessionCreated(session_id=session_id)


@router.get("/session/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, user_id: CurrentUser) -> SessionDetail:
    _, row = _get_chat(session_id, user_id)
    return SessionDetail(
        session_id=session_id,
        status=row["status"],
        messages=row["messages"],
        created_at=row["created_at"],
    )


@router.post("/session/{session_id}/message")
async def send_message(
    session_id: str,
    body: MessageRequest,
    user_id: CurrentUser,
) -> StreamingResponse:
    """
    Send a user message and stream Claude's reply as Server-Sent Events.
    Each SSE event is a text chunk: `data: <chunk>\n\n`
    The client detects REQUIREMENTS_COMPLETE in the stream to know when to show "Finish" button.
    """
    chat, row = _get_chat(session_id, user_id)

    if row["status"] == "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already completed.",
        )

    collected: list[str] = []

    async def event_stream():
        async for chunk in chat.send_message(body.content):
            collected.append(chunk)
            yield f"data: {chunk}\n\n"
        # After streaming, persist updated messages
        _save_messages(session_id, chat.messages)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/session/{session_id}/opening")
async def opening_message(session_id: str, user_id: CurrentUser) -> dict:
    """
    Generate Claude's first message. Returns JSON with the full message.
    """
    chat, row = _get_chat(session_id, user_id)

    if row["messages"]:
        # Already has messages — return the first assistant message
        for msg in row["messages"]:
            if msg["role"] == "assistant":
                return {"message": msg["content"]}

    full_text = ""
    async for chunk in chat.opening_message():
        full_text += chunk
    _save_messages(session_id, chat.messages)
    return {"message": full_text}


@router.post("/session/{session_id}/complete", status_code=status.HTTP_200_OK)
async def complete_session(session_id: str, user_id: CurrentUser) -> dict:
    """
    Extract the focus text from the conversation, embed it, and write to public.profiles.
    Called when the user taps "Finish" in the app after REQUIREMENTS_COMPLETE appears.
    """
    chat, row = _get_chat(session_id, user_id)

    if not chat.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages in session.",
        )

    # Extract focus text from conversation
    focus_text = chat.extract_requirements_summary()

    # Embed focus text
    from openai import OpenAI
    openai_client = OpenAI(api_key=settings.openai_api_key)
    from research_agent.profile import ResearchProfile
    profile = ResearchProfile.create(focus_text=focus_text, openai_client=openai_client)

    # Upsert into public.profiles
    sb = get_admin_client()
    sb.table("profiles").upsert(
        {
            "user_id": user_id,
            "focus_text": focus_text,
            "embedding": profile.embedding,
        },
        on_conflict="user_id",
    ).execute()

    # Mark session complete
    _save_messages(session_id, chat.messages, status_str="complete")

    # Rebuild APScheduler to include this new user
    from ..pipeline.scheduler import rebuild_schedule
    await rebuild_schedule()

    return {"focus_text": focus_text}
