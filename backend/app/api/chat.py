from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_required, get_owned_session
from app.db.session import get_db
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.dialogue_state import handle_turn
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> ChatResponse:
    # Only the logged-in owner may continue a conversation — a session id
    # alone used to be enough.
    session = await get_owned_session(payload.session_id, db, user)
    if session.ended_at:
        # The user chose "结束对话"; an ended conversation is read-only.
        raise HTTPException(status_code=409, detail="session ended")

    confirmation = payload.confirmation.model_dump() if payload.confirmation else None

    if payload.message:
        db.add(Message(session_id=session.id, role=MessageRole.USER, content=payload.message))
        session.participated = True

    try:
        result = await handle_turn(db, session, payload.message, confirmation)
    except LLMUnavailable as e:
        # A clean 503 instead of an unhandled 500: it passes through the CORS
        # middleware, so the browser shows the real reason rather than a
        # misleading CORS error. Not 502: Cloudflare replaces an origin's
        # 502/504 with its own error page, dropping the CORS headers and the
        # reason. Nothing from this turn is saved; the client can retry.
        await db.rollback()
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e

    # A confirmation-only turn has no payload.message, but may have sent the
    # LLM a plain-language description of what was confirmed (see
    # dialogue_state._describe_confirmation). Persist that too so later turns'
    # history reconstruction still shows what was picked, not just this reply.
    if not payload.message and result.user_text_used:
        db.add(Message(session_id=session.id, role=MessageRole.USER, content=result.user_text_used))
        session.participated = True

    db.add(
        Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=result.reply_text,
            meta={
                "candidates": result.candidates,
                "risk_level": result.risk_level.value,
                "prompt_versions": result.prompt_versions,
                "model": result.model,
                "stage": result.stage,
            },
        )
    )
    if confirmation and confirmation.get("card_type") == "end":
        # Only marks the conversation finished — the turns stay, exactly as
        # for a conversation the user simply left (unlike consent.end_session,
        # which also purges them without DIALOGUE_HISTORY consent).
        session.ended_at = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()

    # Design principle 8.2/8.5: Message rows are working memory for this
    # session; they are only kept past session end if the user has opted in
    # via ConsentCategory.DIALOGUE_HISTORY — enforced in app/api/consent.py's
    # `end_session`, not here.

    return ChatResponse(reply_text=result.reply_text, candidates=result.candidates, risk_level=result.risk_level)
