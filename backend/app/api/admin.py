from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required, get_session_or_404
from app.db.session import get_db
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.admin import AdminSessionItem
from app.schemas.chat import HistoryMessageItem

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sessions", response_model=list[AdminSessionItem])
async def list_all_sessions(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[AdminSessionItem]:
    """De-identified, for research analysis (see documents/Modified_Log.md).
    No email or other directly-identifying field is returned — each
    participant is a short, non-reversible-in-the-UI label derived from
    their user_id. Only sessions with at least one message are listed:
    a session with none either never had a message, or had DIALOGUE_HISTORY
    consent revoked/never granted, and its messages were already purged
    (see app/api/chat.py, app/api/consent.py) — this endpoint doesn't
    override that choice."""

    count_subq = (
        select(Message.session_id, func.count(Message.id).label("message_count"))
        .group_by(Message.session_id)
        .subquery()
    )
    result = await db.execute(
        select(ConversationSession, count_subq.c.message_count)
        .join(count_subq, count_subq.c.session_id == ConversationSession.id)
        .order_by(ConversationSession.created_at.desc())
    )
    return [
        AdminSessionItem(
            session_id=session.id,
            participant_label=f"P-{(session.user_id or 'anon')[:8]}",
            language=session.language,
            created_at=session.created_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            message_count=message_count,
        )
        for session, message_count in result.all()
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[HistoryMessageItem])
async def get_admin_session_messages(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
    _admin: User = Depends(get_current_admin_required),
) -> list[HistoryMessageItem]:
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at.asc())
    )
    return [
        HistoryMessageItem(role=m.role.value, content=m.content, created_at=m.created_at.isoformat())
        for m in result.scalars().all()
    ]
