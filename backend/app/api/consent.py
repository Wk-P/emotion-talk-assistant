from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_session
from app.db.session import get_db
from app.models.enums import ConsentCategory
from app.models.message import Message
from app.models.session import ConversationSession
from app.schemas.consent import ConsentStateResponse, ConsentUpdateRequest

router = APIRouter(prefix="/api/session", tags=["consent"])


@router.put("/{session_id}/consent", response_model=ConsentStateResponse)
async def update_consent(
    payload: ConsentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> ConsentStateResponse:
    """PRD 8.5/8.6: the user can grant or revoke each data-use category at any
    time. Revoking DIALOGUE_HISTORY here immediately purges stored turns —
    consent is enforced in code, not left to a prompt."""

    consent = dict(session.consent or {})
    consent[payload.category.value] = payload.granted
    session.consent = consent
    db.add(session)

    if payload.category == ConsentCategory.DIALOGUE_HISTORY and not payload.granted:
        await db.execute(delete(Message).where(Message.session_id == session.id))

    await db.commit()
    return ConsentStateResponse(consent=session.consent)


@router.post("/{session_id}/end")
async def end_session(
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> dict[str, str]:
    """Purges ephemeral working data (raw dialogue turns) unless the user has
    opted in to keeping them. Saved records (app/api/records.py) are a
    separate, always-explicit opt-in and are untouched here."""

    from datetime import datetime, timezone

    consent = session.consent or {}
    if not consent.get(ConsentCategory.DIALOGUE_HISTORY.value, False):
        await db.execute(delete(Message).where(Message.session_id == session.id))

    session.ended_at = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()
    return {"status": "ended"}
