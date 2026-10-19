from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import kst_iso, kst_iso_or_none
from app.api.deps import get_current_user_required, get_owned_session
from app.db.session import get_db
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.summary_card import SummaryCard
from app.models.user import User
from app.schemas.chat import (
    CardDecisionRequest,
    HistoryMessageItem,
    SessionCreateRequest,
    SessionHistoryItem,
    SessionResponse,
    SessionSyncResponse,
    SummaryCardItem,
)
from app.services import summary_card
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/api/session", tags=["session"])

HISTORY_TITLE_LENGTH = 40


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
        await db.execute(delete(SummaryCard).where(SummaryCard.session_id.in_(blank)))
        await db.execute(delete(ConversationSession).where(ConversationSession.id.in_(blank)))

    # There's no fixed opening message any more — the conversation is created
    # empty, and the user's first real message (POST /api/chat) goes straight
    # to handle_turn, same as every later turn.
    session = ConversationSession(language=payload.language, user_id=user.id, consent={})
    db.add(session)
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

    stats_subq = (
        select(
            Message.session_id,
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_at"),
        )
        .group_by(Message.session_id)
        .subquery()
    )
    result = await db.execute(
        select(ConversationSession, func.coalesce(stats_subq.c.message_count, 0), stats_subq.c.last_at)
        .outerjoin(stats_subq, stats_subq.c.session_id == ConversationSession.id)
        .where(owner_filter, ConversationSession.participated.is_(True))
    )
    rows = result.all()

    # First user message of each listed conversation, for its title.
    titles: dict[str, str] = {}
    if rows:
        first = await db.execute(
            select(Message.session_id, Message.content)
            .where(Message.session_id.in_([s.id for s, _, _ in rows]), Message.role == MessageRole.USER)
            .order_by(Message.created_at.asc())
        )
        for session_id, content in first.all():
            titles.setdefault(session_id, " ".join(content.split())[:HISTORY_TITLE_LENGTH])

    items = [
        (last_at or session.created_at, session, message_count) for session, message_count, last_at in rows
    ]
    items.sort(key=lambda x: kst_iso(x[0]), reverse=True)
    return [
        SessionHistoryItem(
            session_id=session.id,
            language=session.language,
            created_at=kst_iso(session.created_at),
            ended_at=kst_iso_or_none(session.ended_at),
            message_count=message_count,
            last_active_at=kst_iso(last_active),
            title=titles.get(session.id, ""),
        )
        for last_active, session, message_count in items
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
        HistoryMessageItem(id=m.id, role=m.role.value, content=m.content, created_at=kst_iso(m.created_at))
        for m in result.scalars().all()
    ]


@router.get("/{session_id}/sync", response_model=SessionSyncResponse)
async def sync_session(
    after: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> SessionSyncResponse:
    """Polled by an open chat so a conversation continued on another device
    shows up here too: only what came after the `after` messages it has."""

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]))
        .order_by(Message.created_at.asc())
    )
    rows = result.scalars().all()
    return SessionSyncResponse(
        messages=[
            HistoryMessageItem(id=m.id, role=m.role.value, content=m.content, created_at=kst_iso(m.created_at))
            for m in rows[after:]
        ],
        total=len(rows),
        ended=session.ended_at is not None,
    )


@router.delete("/history", status_code=204)
async def clear_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> None:
    """User-facing 'clear my records' control. Deletes everything owned by
    this account: messages, cards, saved records (also those whose
    conversation is already gone), and the sessions themselves.
    SQLite's ON DELETE CASCADE is not reliable via aiosqlite here, so each
    table is cleared explicitly rather than relying on FK cascade."""

    owner_filter = ConversationSession.user_id == user.id
    session_ids_subq = select(ConversationSession.id).where(owner_filter).subquery()
    await db.execute(delete(Message).where(Message.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(SummaryCard).where(SummaryCard.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(SavedRecord).where(SavedRecord.session_id.in_(select(session_ids_subq))))
    await db.execute(delete(SavedRecord).where(SavedRecord.user_id == user.id))
    await db.execute(delete(ConversationSession).where(owner_filter))
    await db.commit()


# Declared after DELETE /history so that path isn't read as a session id.
@router.delete("/{session_id}", status_code=204)
async def delete_session(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> None:
    """Delete one of the caller's own conversations and its cards. What the
    user saved to "我的记录" from it stays — they chose to keep that, and
    delete it there. Same rule for every role: you can only delete your own
    here (admins remove others' via /api/admin)."""

    await db.execute(delete(Message).where(Message.session_id == session.id))
    await db.execute(delete(SummaryCard).where(SummaryCard.session_id == session.id))
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

    if session.ended_at:
        # Ended (终止) conversations are sealed — nothing about them changes.
        raise HTTPException(status_code=409, detail="session ended")
    session.language = payload.language
    db.add(session)
    await db.commit()
    return SessionResponse(session_id=session.id, language=session.language)


def _card_item(card: SummaryCard) -> SummaryCardItem:
    return SummaryCardItem.model_validate(
        {
            "id": card.id,
            "kind": card.kind,
            "content": card.content or {},
            "after_messages": card.after_messages,
            "decision": card.decision,
        }
    )


@router.get("/{session_id}/cards", response_model=list[SummaryCardItem])
async def list_cards(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> list[SummaryCardItem]:
    """The conversation cards shown so far, for reopening a conversation."""

    return [_card_item(c) for c in await summary_card.list_cards(db, session.id)]


@router.post("/{session_id}/review-card", response_model=SummaryCardItem | None)
async def review_card(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> SummaryCardItem | None:
    """Asked whenever the user opens or comes back to a conversation; the
    program decides whether a review card is due (app/services/summary_card.py).
    null when it isn't."""

    try:
        card = await summary_card.review_card(db, session)
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e
    return _card_item(card) if card else None


@router.post("/{session_id}/final-card", response_model=SummaryCardItem)
async def final_card(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> SummaryCardItem:
    """The card shown after the user ended the conversation (written once)."""

    if not session.ended_at:
        raise HTTPException(status_code=409, detail="session not ended")
    try:
        card = await summary_card.final_card(db, session)
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e
    return _card_item(card)


@router.post("/{session_id}/cards/{card_id}/decision", status_code=204)
async def decide_card(
    card_id: str,
    payload: CardDecisionRequest,
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> Response:
    """The user's pick on the final card: keep it in "我的记录" or not."""

    card = await db.get(SummaryCard, card_id)
    if card is None or card.session_id != session.id or card.kind != "final":
        raise HTTPException(status_code=404, detail="card not found")
    if card.decision is None:
        await summary_card.decide(db, session, card, payload.save)
    return Response(status_code=204)
