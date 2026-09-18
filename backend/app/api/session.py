from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_session_or_404
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
    user: User | None = Depends(get_current_user_optional),
) -> SessionResponse:
    session = ConversationSession(
        language=payload.language,
        device_id=payload.device_id,
        user_id=user.id if user else None,
        consent={},
        confirmed_context={},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(session_id=session.id, language=session.language)


@router.get("/history", response_model=list[SessionHistoryItem])
async def list_history(
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> list[SessionHistoryItem]:
    """History is scoped by account when logged in (works across devices),
    otherwise falls back to the client-generated, no-login device_id (see
    ConversationSession.device_id) — anyone who knows a device_id can read
    its history, which is acceptable only because it isn't a real identity."""

    if user is None and not device_id:
        raise HTTPException(status_code=400, detail="device_id is required when not logged in")

    count_subq = (
        select(Message.session_id, func.count(Message.id).label("message_count"))
        .group_by(Message.session_id)
        .subquery()
    )
    owner_filter = ConversationSession.user_id == user.id if user else ConversationSession.device_id == device_id
    result = await db.execute(
        select(ConversationSession, func.coalesce(count_subq.c.message_count, 0))
        .outerjoin(count_subq, count_subq.c.session_id == ConversationSession.id)
        .where(owner_filter)
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
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> None:
    """User-facing 'clear my records' control — see list_history for how the
    owner (account vs device_id) is determined. Deletes everything owned:
    messages, saved records, and the sessions themselves. SQLite's ON DELETE
    CASCADE is not reliable via aiosqlite here, so each table is cleared
    explicitly rather than relying on FK cascade."""

    if user is None and not device_id:
        raise HTTPException(status_code=400, detail="device_id is required when not logged in")

    owner_filter = ConversationSession.user_id == user.id if user else ConversationSession.device_id == device_id
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
