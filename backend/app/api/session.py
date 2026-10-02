from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_required, get_owned_session
from app.db.session import get_db
from app.models.enums import Language, MessageRole
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.chat import ChatResponse, HistoryMessageItem, SessionCreateRequest, SessionHistoryItem, SessionResponse
from app.services.dialogue_state import opening_turn

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("/opening", response_model=ChatResponse)
async def get_opening(language: Language = Language.ZH, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """What a new chat shows before the user has said anything — read-only,
    nothing is stored. Like ChatGPT, a conversation only gets created
    (POST /start) once the user sends their first message or picks an option."""

    turn = await opening_turn(db, language)
    return ChatResponse(reply_text=turn.reply_text, candidates=turn.candidates, risk_level=turn.risk_level)


@router.post("/start", response_model=SessionResponse)
async def start_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> SessionResponse:
    # Clean up this owner's earlier chats that were started but never used
    # (no user message) — they're hidden everywhere already, this just keeps
    # them from piling up in the database.
    owner_filter = ConversationSession.user_id == user.id
    blank_ids = select(ConversationSession.id).where(owner_filter, ConversationSession.participated.is_(False))
    blank = list((await db.execute(blank_ids)).scalars().all())
    if blank:
        await db.execute(delete(Message).where(Message.session_id.in_(blank)))
        await db.execute(delete(SavedRecord).where(SavedRecord.session_id.in_(blank)))
        await db.execute(delete(ConversationSession).where(ConversationSession.id.in_(blank)))

    session = ConversationSession(
        language=payload.language,
        user_id=user.id,
        consent={},
        confirmed_context={"disclaimer_shown": True},
    )
    db.add(session)
    await db.flush()
    # The client already showed this opening from GET /opening before the
    # session existed; record it here so the stored transcript starts where
    # the conversation the user saw did.
    opening = await opening_turn(db, session.language)
    db.add(
        Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=opening.reply_text,
            meta={"candidates": opening.candidates, "risk_level": opening.risk_level.value, "prompt_versions": opening.prompt_versions},
        )
    )
    await db.commit()
    await db.refresh(session)
    return SessionResponse(session_id=session.id, language=session.language)


@router.get("/history", response_model=list[SessionHistoryItem])
async def list_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> list[SessionHistoryItem]:
    """The caller's own conversations, on whichever device they were held."""

    owner_filter = ConversationSession.user_id == user.id

    count_subq = (
        select(Message.session_id, func.count(Message.id).label("message_count"))
        .group_by(Message.session_id)
        .subquery()
    )
    result = await db.execute(
        select(ConversationSession, func.coalesce(count_subq.c.message_count, 0))
        .outerjoin(count_subq, count_subq.c.session_id == ConversationSession.id)
        .where(owner_filter, ConversationSession.participated.is_(True))
        .order_by(ConversationSession.created_at.desc())
    )
    return [
        SessionHistoryItem(
            session_id=session.id,
            language=session.language,
            created_at=session.created_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            message_count=message_count,
        )
        for session, message_count in result.all()
    ]


@router.get("/{session_id}/messages", response_model=list[HistoryMessageItem])
async def get_session_messages(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> list[HistoryMessageItem]:
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at.asc())
    )
    return [
        HistoryMessageItem(role=m.role.value, content=m.content, created_at=m.created_at.isoformat())
        for m in result.scalars().all()
    ]


@router.delete("/history", status_code=204)
async def clear_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> None:
    """User-facing 'clear my records' control. Deletes everything owned by
    this account: messages, saved records, and the sessions themselves.
    SQLite's ON DELETE CASCADE is not reliable via aiosqlite here, so each
    table is cleared explicitly rather than relying on FK cascade."""

    owner_filter = ConversationSession.user_id == user.id
    session_ids_subq = select(ConversationSession.id).where(owner_filter).subquery()
    await db.execute(delete(Message).where(Message.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(ConversationSession).where(owner_filter))
    await db.commit()


# Declared after DELETE /history so that path isn't read as a session id.
@router.delete("/{session_id}", status_code=204)
async def delete_session(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> None:
    """Delete one of the caller's own conversations — its messages and the
    records saved from it go too. Same rule for every role: you can only
    delete your own here (admins remove others' via /api/admin)."""

    await db.execute(delete(Message).where(Message.session_id == session.id))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id == session.id))
    await db.execute(delete(ConversationSession).where(ConversationSession.id == session.id))
    await db.commit()


@router.put("/{session_id}/language", response_model=SessionResponse)
async def update_language(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> SessionResponse:
    """Design principle 10.5: switching zh/ko mid-conversation must not
    re-derive or reclassify anything already confirmed — only which language
    future replies are generated in changes."""

    session.language = payload.language
    db.add(session)
    await db.commit()
    return SessionResponse(session_id=session.id, language=session.language)
