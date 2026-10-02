from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required, get_session_or_404
from app.db.session import get_db
from app.models.enums import Language, UserRole
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.reflection import DailyReflection
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.admin import (
    AdminMessageItem,
    AdminRecordItem,
    AdminSessionExport,
    AdminSessionItem,
    AdminUserItem,
    CreateUserRequest,
    ResetPasswordRequest,
    SetActiveRequest,
    SetRoleRequest,
)
from app.services.auth import hash_password, normalize_username
from app.api.reflections import to_item as _reflection_item
from app.schemas.reflection import AdminReflectionItem
from app.services import export_docs
from app.services.crypto import decrypt_json

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin_message(m: Message) -> AdminMessageItem:
    return AdminMessageItem(
        role=m.role.value,
        content=m.content,
        created_at=m.created_at.isoformat(),
        prompt_versions=(m.meta or {}).get("prompt_versions"),
    )


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


def _can_view(actor: User, target: User) -> None:
    """Read-only counterpart of _can_manage, for per-user export: the same
    accounts an admin sees in GET /users (plus their own)."""

    if target.id == actor.id:
        return
    if target.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="cannot act on a superadmin account")
    if actor.role != UserRole.SUPERADMIN and target.role != UserRole.USER:
        raise HTTPException(status_code=403, detail="admin access required")


def _admin_record(r: SavedRecord) -> AdminRecordItem:
    return AdminRecordItem(
        id=r.id,
        record_type=r.record_type.value,
        payload=decrypt_json(r.payload_encrypted),
        created_at=r.created_at.isoformat(),
    )


async def _record_counts(db: AsyncSession, session_ids: list[str]) -> dict[str, int]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(SavedRecord.session_id, func.count(SavedRecord.id))
        .where(SavedRecord.session_id.in_(session_ids))
        .group_by(SavedRecord.session_id)
    )
    return dict(result.all())


def _participant_label(session: ConversationSession) -> str:
    return f"P-{(session.user_id or 'anon')[:8]}"


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_utc_naive(value: datetime) -> datetime:
    # SQLite stores created_at as naive UTC text; comparing against an aware
    # datetime would compare strings in different formats.
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


@dataclass
class SessionFilter:
    """Shared by GET /sessions and GET /export, so "export" always means
    "export exactly what the list currently shows"."""

    participant: str | None = None
    user_id: str | None = None
    language: Language | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_messages: int | None = None


def session_filter(
    participant: str | None = Query(default=None, max_length=40, description="匿名编号，如 P-1a2b3c4d，可只填前几位"),
    user_id: str | None = Query(default=None, max_length=36),
    language: Language | None = None,
    created_from: datetime | None = Query(default=None, description="开始时间（含）"),
    created_to: datetime | None = Query(default=None, description="结束时间（不含）"),
    min_messages: int | None = Query(default=None, ge=1),
) -> SessionFilter:
    return SessionFilter(participant, user_id, language, created_from, created_to, min_messages)


async def _apply_session_filter(
    stmt: Select, f: SessionFilter, message_count, db: AsyncSession, admin: User
) -> Select:
    if f.participant:
        code = f.participant.strip().lower().removeprefix("p-")
        if code == "anon":
            stmt = stmt.where(ConversationSession.user_id.is_(None))
        elif code:
            stmt = stmt.where(ConversationSession.user_id.like(f"{_like_escape(code)}%", escape="\\"))
    if f.user_id:
        _can_view(admin, await _get_user_or_404(f.user_id, db))
        stmt = stmt.where(ConversationSession.user_id == f.user_id)
    if f.language:
        stmt = stmt.where(ConversationSession.language == f.language)
    if f.created_from:
        stmt = stmt.where(ConversationSession.created_at >= _to_utc_naive(f.created_from))
    if f.created_to:
        stmt = stmt.where(ConversationSession.created_at < _to_utc_naive(f.created_to))
    if f.min_messages:
        stmt = stmt.where(message_count >= f.min_messages)
    return stmt


def _message_count_subquery():
    return (
        select(Message.session_id, func.count(Message.id).label("message_count"))
        .group_by(Message.session_id)
        .subquery()
    )


async def _user_item(db: AsyncSession, user: User) -> AdminUserItem:
    session_count = await db.execute(
        select(func.count(ConversationSession.id)).where(
            ConversationSession.user_id == user.id, ConversationSession.participated.is_(True)
        )
    )
    return AdminUserItem(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        session_count=session_count.scalar_one(),
    )


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
    await db.execute(delete(DailyReflection).where(DailyReflection.user_id == user_id))


@router.get("/sessions", response_model=list[AdminSessionItem])
async def list_all_sessions(
    f: SessionFilter = Depends(session_filter),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> list[AdminSessionItem]:
    """De-identified, for research analysis (see documents/Modified_Log.md).
    No username or other directly-identifying field is returned — each
    participant is a short, non-reversible-in-the-UI label derived from
    their user_id. Only sessions the user took part in (see
    ConversationSession.participated) and that still have messages are listed:
    a session with none either never had a message, or had DIALOGUE_HISTORY
    consent revoked/never granted, and its messages were already purged
    (see app/api/chat.py, app/api/consent.py) — this endpoint doesn't
    override that choice."""

    count_subq = _message_count_subquery()
    stmt = (
        select(ConversationSession, count_subq.c.message_count)
        .join(count_subq, count_subq.c.session_id == ConversationSession.id)
        .where(ConversationSession.participated.is_(True))
        .order_by(ConversationSession.created_at.desc())
    )
    stmt = await _apply_session_filter(stmt, f, count_subq.c.message_count, db, admin)
    rows = (await db.execute(stmt)).all()
    record_counts = await _record_counts(db, [session.id for session, _ in rows])
    return [
        AdminSessionItem(
            session_id=session.id,
            participant_label=_participant_label(session),
            language=session.language,
            created_at=session.created_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            message_count=message_count,
            record_count=record_counts.get(session.id, 0),
        )
        for session, message_count in rows
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[AdminMessageItem])
async def get_admin_session_messages(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
    _admin: User = Depends(get_current_admin_required),
) -> list[AdminMessageItem]:
    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at.asc())
    )
    return [_admin_message(m) for m in result.scalars().all()]


@router.get("/sessions/{session_id}/records", response_model=list[AdminRecordItem])
async def get_admin_session_records(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
    _admin: User = Depends(get_current_admin_required),
) -> list[AdminRecordItem]:
    result = await db.execute(
        select(SavedRecord).where(SavedRecord.session_id == session.id).order_by(SavedRecord.created_at.asc())
    )
    return [_admin_record(r) for r in result.scalars().all()]


@router.get("/export", response_model=list[AdminSessionExport])
async def export_all_sessions(
    f: SessionFilter = Depends(session_filter),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> list[AdminSessionExport]:
    """De-identified sessions with their messages inlined, in one call —
    backs the export buttons so research analysis doesn't need a
    session-by-session fetch loop client-side. Takes the same filters as
    GET /sessions; `participant` or `user_id` gives a single-user export."""

    count_subq = _message_count_subquery()
    stmt = (
        select(ConversationSession)
        .join(count_subq, count_subq.c.session_id == ConversationSession.id)
        .where(ConversationSession.participated.is_(True))
        .order_by(ConversationSession.created_at.desc())
    )
    stmt = await _apply_session_filter(stmt, f, count_subq.c.message_count, db, admin)
    sessions = (await db.execute(stmt)).scalars().all()

    messages_result = await db.execute(
        select(Message).where(Message.session_id.in_([s.id for s in sessions])).order_by(Message.created_at.asc())
    )
    messages_by_session: dict[str, list[Message]] = {}
    for m in messages_result.scalars().all():
        messages_by_session.setdefault(m.session_id, []).append(m)

    records_result = await db.execute(
        select(SavedRecord)
        .where(SavedRecord.session_id.in_([s.id for s in sessions]))
        .order_by(SavedRecord.created_at.asc())
    )
    records_by_session: dict[str, list[SavedRecord]] = {}
    for rec in records_result.scalars().all():
        records_by_session.setdefault(rec.session_id, []).append(rec)

    return [
        AdminSessionExport(
            session_id=session.id,
            participant_label=_participant_label(session),
            language=session.language,
            created_at=session.created_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            messages=[_admin_message(m) for m in messages_by_session.get(session.id, [])],
            records=[_admin_record(rec) for rec in records_by_session.get(session.id, [])],
        )
        for session in sessions
    ]


_EXPORT_FORMATS = {
    # format: (renderer, media type, file extension)
    "md": (export_docs.to_markdown, "text/markdown; charset=utf-8", "md"),
    "txt": (export_docs.to_text, "text/plain; charset=utf-8", "txt"),
    "docx": (
        export_docs.to_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "pdf": (export_docs.to_pdf, "application/pdf", "pdf"),
}


@router.get("/export/file")
async def export_sessions_file(
    format: Literal["md", "txt", "docx", "pdf"],
    lang: Literal["zh", "ko"] = "zh",
    tz_offset: int = Query(default=0, ge=-840, le=840, description="浏览器 getTimezoneOffset()，用于显示本地时间"),
    name: str = Query(default="export", max_length=60, pattern=r"^[A-Za-z0-9_.-]+$"),
    f: SessionFilter = Depends(session_filter),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> Response:
    """The same export as GET /export (same filters, same permissions), as
    a readable document instead of JSON: Markdown, plain text, Word or PDF."""

    sessions = await export_all_sessions(f=f, db=db, admin=admin)
    render, media_type, ext = _EXPORT_FORMATS[format]
    content = render(sessions, lang, tz_offset)
    filename = f"emotion-ai-{name}-{datetime.now().strftime('%Y-%m-%d')}.{ext}"
    return Response(
        content=content.encode("utf-8") if isinstance(content, str) else content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/reflections", response_model=list[AdminReflectionItem])
async def list_reflections(
    participant: str | None = Query(default=None, max_length=40),
    day_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    day_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[AdminReflectionItem]:
    """每日省察 answers for research review, newest first. De-identified
    like the conversation list: participants appear only as P-xxxxxxxx."""

    stmt = select(DailyReflection).order_by(DailyReflection.day.desc(), DailyReflection.created_at.desc())
    if participant:
        code = participant.strip().lower().removeprefix("p-")
        if code == "anon":
            stmt = stmt.where(DailyReflection.user_id.is_(None))
        elif code:
            stmt = stmt.where(DailyReflection.user_id.like(f"{_like_escape(code)}%", escape="\\"))
    if day_from:
        stmt = stmt.where(DailyReflection.day >= day_from)
    if day_to:
        stmt = stmt.where(DailyReflection.day <= day_to)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        AdminReflectionItem(**_reflection_item(r).model_dump(), participant_label=f"P-{(r.user_id or 'anon')[:8]}")
        for r in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_admin_session(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_session_or_404),
    admin: User = Depends(get_current_admin_required),
) -> None:
    # Deleting your own conversation isn't a self-account action (no
    # demotion/disable/deletion of the account itself), so it's exempt from
    # _can_manage's self-guard — otherwise an admin could never clear their
    # own test conversations.
    if session.user_id and session.user_id != admin.id:
        owner = await db.get(User, session.user_id)
        if owner is not None:
            _can_manage(admin, owner)

    await db.execute(delete(Message).where(Message.session_id == session.id))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id == session.id))
    await db.execute(delete(ConversationSession).where(ConversationSession.id == session.id))
    await db.commit()


@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    q: str | None = Query(default=None, max_length=100, description="按 ID 搜索（包含即可）"),
    role: UserRole | None = None,
    status: Literal["active", "disabled"] | None = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> list[AdminUserItem]:
    """A plain admin only ever sees plain-user accounts; a superadmin also
    sees other admins (never other superadmins — see _can_manage). The
    filters only ever narrow that visible set."""

    visible_roles = (
        [UserRole.USER, UserRole.ADMIN] if admin.role == UserRole.SUPERADMIN else [UserRole.USER]
    )
    if role is not None:
        visible_roles = [r for r in visible_roles if r == role]
    count_subq = (
        select(ConversationSession.user_id, func.count(ConversationSession.id).label("session_count"))
        .where(ConversationSession.participated.is_(True))
        .group_by(ConversationSession.user_id)
        .subquery()
    )
    stmt = (
        select(User, func.coalesce(count_subq.c.session_count, 0))
        .outerjoin(count_subq, count_subq.c.user_id == User.id)
        .where(User.role.in_(visible_roles))
        .order_by(User.created_at.desc())
    )
    if q and q.strip():
        stmt = stmt.where(User.username.ilike(f"%{_like_escape(q.strip())}%", escape="\\"))
    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "disabled":
        stmt = stmt.where(User.is_active.is_(False))
    result = await db.execute(stmt)
    return [
        AdminUserItem(
            id=user.id,
            username=user.username,
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
    return await _user_item(db, target)


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
    return await _user_item(db, target)


@router.post("/users", response_model=AdminUserItem, status_code=201)
async def create_user(
    payload: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> AdminUserItem:
    """For accounts set up on someone's behalf (users can also register
    themselves). A plain admin can create plain users; a superadmin can also
    create admins. Superadmins are still DB-only, as with set_user_role."""

    if payload.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=400, detail="creating a superadmin requires direct database access")
    if payload.role == UserRole.ADMIN and admin.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="superadmin access required")

    username = normalize_username(payload.username)
    if (await db.execute(select(User.id).where(User.username == username))).first() is not None:
        raise HTTPException(status_code=409, detail="username already taken")

    user = User(username=username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _user_item(db, user)


@router.post("/users/{user_id}/password", response_model=AdminUserItem)
async def reset_user_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> AdminUserItem:
    """There's no email to send a reset link to: a user who forgot their
    password asks an admin, who sets a new one and passes it on."""

    target = await _get_user_or_404(user_id, db)
    _can_manage(admin, target)
    target.password_hash = hash_password(payload.password)
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return await _user_item(db, target)
