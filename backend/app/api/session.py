from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_required, get_session_or_404
from app.db.session import get_db
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.chat import HistoryMessageItem, SessionCreateRequest, SessionHistoryItem, SessionResponse

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/start", response_model=SessionResponse)
async def start_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> SessionResponse:
    session = ConversationSession(
        language=payload.language,
        user_id=user.id,
        consent={},
        confirmed_context={},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(session_id=session.id, language=session.language)


@router.get("/history", response_model=list[SessionHistoryItem])
async def list_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> list[SessionHistoryItem]:
    """No more anonymous, device_id-scoped history: every session now
    requires a logged-in account (see start_session), so history is always
    scoped by user_id."""

    count_subq = (
        select(Message.session_id, func.count(Message.id).label("message_count"))
        .group_by(Message.session_id)
        .subquery()
    )
    result = await db.execute(
        select(ConversationSession, func.coalesce(count_subq.c.message_count, 0))
        .outerjoin(count_subq, count_subq.c.session_id == ConversationSession.id)
        .where(ConversationSession.user_id == user.id)
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
    session: ConversationSession = Depends(get_session_or_404),
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


@router.put("/{session_id}/language", response_model=SessionResponse)
async def update_language(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
) -> SessionResponse:
    """Design principle 10.5: switching zh/ko mid-conversation must not
    re-derive or reclassify anything already confirmed — only which language
    future replies are generated in changes."""

    session.language = payload.language
    db.add(session)
    await db.commit()
    return SessionResponse(session_id=session.id, language=session.language)
