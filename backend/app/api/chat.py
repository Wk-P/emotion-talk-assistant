from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.session import ConversationSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.dialogue_state import handle_turn

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    session_query = await db.execute(select(ConversationSession).where(ConversationSession.id == payload.session_id))
    session = session_query.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    confirmation = payload.confirmation.model_dump() if payload.confirmation else None

    if payload.message:
        db.add(Message(session_id=session.id, role=MessageRole.USER, content=payload.message))

    result = await handle_turn(db, session, payload.message, confirmation)

    # A confirmation-only turn has no payload.message, but may have sent the
    # LLM a plain-language description of what was confirmed (see
    # dialogue_state._describe_confirmation). Persist that too so later turns'
    # history reconstruction still shows what was picked, not just this reply.
    if not payload.message and result.user_text_used:
        db.add(Message(session_id=session.id, role=MessageRole.USER, content=result.user_text_used))

    db.add(
        Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=result.reply_text,
            meta={
                "candidates": result.candidates,
                "risk_level": result.risk_level.value,
                "prompt_versions": result.prompt_versions,
            },
        )
    )
    db.add(session)
    await db.commit()

    # Design principle 8.2/8.5: Message rows are working memory for this
    # session; they are only kept past session end if the user has opted in
    # via ConsentCategory.DIALOGUE_HISTORY — enforced in app/api/consent.py's
    # `end_session`, not here.

    return ChatResponse(reply_text=result.reply_text, candidates=result.candidates, risk_level=result.risk_level)
