from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required, get_session_or_404
from app.db.session import get_db
from app.models.auth_token import AuthToken
from app.models.enums import UserRole
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.admin import AdminSessionExport, AdminSessionItem, AdminUserItem, SetActiveRequest, SetRoleRequest
from app.schemas.chat import HistoryMessageItem

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _can_manage(actor: User, target: User) -> None:
    """Shared gate for every user-management action below. Nobody — not even
    a superadmin — can act on a superadmin account through this API; that
    role change only ever happens by direct DB access (see UserRole's
    docstring). A plain admin is further limited to plain-user targets."""

    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="cannot act on your own account")
    if target.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="cannot act on a superadmin account")
    if actor.role != UserRole.SUPERADMIN and target.role != UserRole.USER:
        raise HTTPException(status_code=403, detail="admin access required")


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


async def _delete_user_data(db: AsyncSession, user_id: str) -> None:
    session_ids_subq = select(ConversationSession.id).where(ConversationSession.user_id == user_id).subquery()
    await db.execute(delete(Message).where(Message.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(ConversationSession).where(ConversationSession.user_id == user_id))
    await db.execute(delete(AuthToken).where(AuthToken.user_id == user_id))


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


@router.get("/export", response_model=list[AdminSessionExport])
async def export_all_sessions(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[AdminSessionExport]:
    """Every de-identified session with its messages inlined, in one call —
    backs the 'export JSON' button so research analysis doesn't need a
    session-by-session fetch loop client-side."""

    sessions_result = await db.execute(
        select(ConversationSession)
        .join(Message, Message.session_id == ConversationSession.id)
        .distinct()
        .order_by(ConversationSession.created_at.desc())
    )
    sessions = sessions_result.scalars().all()

    messages_result = await db.execute(
        select(Message).where(Message.session_id.in_([s.id for s in sessions])).order_by(Message.created_at.asc())
    )
    messages_by_session: dict[str, list[Message]] = {}
    for m in messages_result.scalars().all():
        messages_by_session.setdefault(m.session_id, []).append(m)

    return [
        AdminSessionExport(
            session_id=session.id,
            participant_label=f"P-{(session.user_id or 'anon')[:8]}",
            language=session.language,
            created_at=session.created_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            messages=[
                HistoryMessageItem(role=m.role.value, content=m.content, created_at=m.created_at.isoformat())
                for m in messages_by_session.get(session.id, [])
            ],
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_admin_session(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
    admin: User = Depends(get_current_admin_required),
) -> None:
    if session.user_id:
        owner = await db.get(User, session.user_id)
        if owner is not None:
            _can_manage(admin, owner)

    await db.execute(delete(Message).where(Message.session_id == session.id))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id == session.id))
    await db.execute(delete(ConversationSession).where(ConversationSession.id == session.id))
    await db.commit()


@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> list[AdminUserItem]:
    """A plain admin only ever sees plain-user accounts; a superadmin also
    sees other admins (never other superadmins — see _can_manage)."""

    visible_roles = (
        [UserRole.USER, UserRole.ADMIN] if admin.role == UserRole.SUPERADMIN else [UserRole.USER]
    )
    count_subq = (
        select(ConversationSession.user_id, func.count(ConversationSession.id).label("session_count"))
        .group_by(ConversationSession.user_id)
        .subquery()
    )
    result = await db.execute(
        select(User, func.coalesce(count_subq.c.session_count, 0))
        .outerjoin(count_subq, count_subq.c.user_id == User.id)
        .where(User.role.in_(visible_roles))
        .order_by(User.created_at.desc())
    )
    return [
        AdminUserItem(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            session_count=session_count,
        )
        for user, session_count in result.all()
    ]


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> None:
    target = await _get_user_or_404(user_id, db)
    _can_manage(admin, target)
    await _delete_user_data(db, user_id)
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


@router.patch("/users/{user_id}/active", response_model=AdminUserItem)
async def set_user_active(
    user_id: str,
    payload: SetActiveRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> AdminUserItem:
    target = await _get_user_or_404(user_id, db)
    _can_manage(admin, target)
    target.is_active = payload.is_active
    db.add(target)
    await db.commit()
    await db.refresh(target)
    session_count_result = await db.execute(
        select(func.count(ConversationSession.id)).where(ConversationSession.user_id == user_id)
    )
    return AdminUserItem(
        id=target.id,
        email=target.email,
        email_verified=target.email_verified,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at.isoformat(),
        session_count=session_count_result.scalar_one(),
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
async def set_user_role(
    user_id: str,
    payload: SetRoleRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> AdminUserItem:
    if admin.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="superadmin access required")
    if payload.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=400, detail="promoting to superadmin requires direct database access")

    target = await _get_user_or_404(user_id, db)
    _can_manage(admin, target)
    target.role = payload.role
    db.add(target)
    await db.commit()
    await db.refresh(target)
    session_count_result = await db.execute(
        select(func.count(ConversationSession.id)).where(ConversationSession.user_id == user_id)
    )
    return AdminUserItem(
        id=target.id,
        email=target.email,
        email_verified=target.email_verified,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at.isoformat(),
        session_count=session_count_result.scalar_one(),
    )
