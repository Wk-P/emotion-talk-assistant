"""The conversation card: a short AI-written summary of the conversation
(what happened, the plan — empty when there was none — and a kind word for
oneself). When it is shown is fixed here in code, not by the model:

  - "review": the user is back in a conversation that hasn't ended, at least
    REVIEW_AFTER since its last message, with at least REVIEW_MIN_ROUNDS
    rounds (a user message answered by the AI) since the previous card.
    Only shown, never saved to "我的记录".
  - "final": once, after the user ended the conversation. The user then
    picks whether to keep it in "我的记录".

How the card is written is the admins' (admin page "程序附加说明",
system.summary_card, app/prompts/system.py).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ConsentCategory, Language, MessageRole, RecordType
from app.models.message import Message
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.summary_card import SummaryCard
from app.prompts import registry, system
from app.services import ai_params
from app.services.crypto import encrypt_json
from app.services.llm import generate_json
from app.services.model_settings import current_effort, current_model

REVIEW_AFTER = timedelta(hours=4)
REVIEW_MIN_ROUNDS = 4
FIELDS = ("summary", "plan", "kindness")
PROMPT_KEY = "system.summary_card"

# One card at a time per conversation: two tabs opening it together would
# otherwise both write one.
_locks: dict[str, asyncio.Lock] = {}


def _lock(session_id: str) -> asyncio.Lock:
    return _locks.setdefault(session_id, asyncio.Lock())


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def _talk(db: AsyncSession, session_id: str) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]))
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())


def _rounds(messages: list[Message]) -> int:
    """How many times a user message was answered by the AI."""

    return sum(
        1
        for prev, cur in zip(messages, messages[1:])
        if prev.role == MessageRole.USER and cur.role == MessageRole.ASSISTANT
    )


async def list_cards(db: AsyncSession, session_id: str) -> list[SummaryCard]:
    result = await db.execute(
        select(SummaryCard).where(SummaryCard.session_id == session_id).order_by(SummaryCard.created_at.asc())
    )
    return list(result.scalars().all())


async def _write(db: AsyncSession, language: Language, messages: list[Message]) -> dict[str, str]:
    sys = await registry.system_texts(db, language)
    # Turned off by an admin: the card still has to be written somehow.
    prompt = sys.get(PROMPT_KEY) or system.DEFAULTS[PROMPT_KEY][language]
    if "json" not in prompt.lower():
        prompt += "\n\nJSON"
    you, ai = ("用户", "AI") if language == Language.ZH else ("사용자", "AI")
    transcript = "\n".join(f"{you if m.role == MessageRole.USER else ai}：{m.content}" for m in messages)
    out = await generate_json(
        prompt, transcript, await current_model(db), await current_effort(db), await ai_params.load(db)
    )
    return {k: str(out.get(k) or "").strip() for k in FIELDS}


async def review_card(db: AsyncSession, session: ConversationSession) -> SummaryCard | None:
    """Writes a review card if one is due now (see the module docstring)."""

    if session.ended_at:
        return None
    async with _lock(session.id):
        messages = await _talk(db, session.id)
        if not messages or datetime.now(UTC) - _utc(messages[-1].created_at) < REVIEW_AFTER:
            return None
        start = max((c.after_messages for c in await list_cards(db, session.id)), default=0)
        if _rounds(messages[start:]) < REVIEW_MIN_ROUNDS:
            return None
        card = SummaryCard(
            session_id=session.id,
            kind="review",
            content=await _write(db, session.language, messages),
            after_messages=len(messages),
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)
        return card


async def final_card(db: AsyncSession, session: ConversationSession) -> SummaryCard:
    """The ended conversation's card, written the first time it is asked for."""

    async with _lock(session.id):
        existing = next((c for c in await list_cards(db, session.id) if c.kind == "final"), None)
        if existing:
            return existing
        messages = await _talk(db, session.id)
        card = SummaryCard(
            session_id=session.id,
            kind="final",
            content=await _write(db, session.language, messages),
            after_messages=len(messages),
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)
        return card


async def decide(db: AsyncSession, session: ConversationSession, card: SummaryCard, save: bool) -> None:
    """The user's pick for a final card: keep it in "我的记录" or drop it.
    Choosing to keep it is their consent to keeping this record."""

    if save:
        consent = dict(session.consent or {})
        consent[ConsentCategory.EMOTION_RECORDS.value] = True
        session.consent = consent
        db.add(session)
        db.add(
            SavedRecord(
                session_id=session.id,
                user_id=session.user_id,
                record_type=RecordType.CONVERSATION_SUMMARY,
                payload_encrypted=encrypt_json(dict(card.content)).decode("utf-8"),
                consented_category=ConsentCategory.EMOTION_RECORDS.value,
            )
        )
        card.decision = "saved"
    else:
        card.content = {}
        card.decision = "discarded"
    db.add(card)
    await db.commit()

