from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.enums import ConsentCategory
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.record import OwnRecordItem, RecordResponse, SaveRecordRequest
from app.services.crypto import decrypt_json, encrypt_json

router = APIRouter(prefix="/api/records", tags=["records"])

# Records saved from a self-kindness/self-encouragement/value-goal/recovery-plan
# card fall under EMOTION_RECORDS consent unless they concern acculturation
# problem-type tagging, which is CULTURE_ADAPTATION_INFO instead.
_CULTURE_TAGGED_TYPES = {"cause_interpretation"}


def _owner_filter(user: User | None, device_id: str | None) -> ColumnElement[bool]:
    """Same ownership rule as GET /api/session/history: the account when
    logged in, otherwise the browser's device_id."""

    if user is not None:
        return ConversationSession.user_id == user.id
    if device_id:
        return ConversationSession.device_id == device_id
    raise HTTPException(status_code=400, detail="device_id required when not logged in")


@router.get("", response_model=list[OwnRecordItem])
async def list_my_records(
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> list[OwnRecordItem]:
    """Every record the caller saved, across all their conversations,
    newest first."""

    result = await db.execute(
        select(SavedRecord, ConversationSession.created_at)
        .join(ConversationSession, ConversationSession.id == SavedRecord.session_id)
        .where(_owner_filter(user, device_id))
        .order_by(SavedRecord.created_at.desc())
    )
    return [
        OwnRecordItem(
            id=r.id,
            record_type=r.record_type,
            payload=decrypt_json(r.payload_encrypted),
            created_at=r.created_at,
            session_id=r.session_id,
            session_created_at=session_created_at,
        )
        for r, session_created_at in result.all()
    ]


@router.post("", response_model=RecordResponse, status_code=201)
async def save_record(payload: SaveRecordRequest, db: AsyncSession = Depends(get_db)) -> RecordResponse:
    result = await db.execute(select(ConversationSession).where(ConversationSession.id == payload.session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    category = (
        ConsentCategory.CULTURE_ADAPTATION_INFO
        if payload.record_type.value in _CULTURE_TAGGED_TYPES
        else ConsentCategory.EMOTION_RECORDS
    )
    consent = session.consent or {}
    if not consent.get(category.value, False):
        raise HTTPException(
            status_code=403,
            detail=f"saving this record requires consent for '{category.value}'; "
            f"call PUT /api/session/{{id}}/consent first",
        )

    record = SavedRecord(
        session_id=session.id,
        record_type=payload.record_type,
        payload_encrypted=encrypt_json(payload.payload).decode("utf-8"),
        consented_category=category.value,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return RecordResponse(id=record.id, record_type=record.record_type, payload=payload.payload, created_at=record.created_at)


@router.get("/{session_id}", response_model=list[RecordResponse])
async def list_records(session_id: str, db: AsyncSession = Depends(get_db)) -> list[RecordResponse]:
    result = await db.execute(select(SavedRecord).where(SavedRecord.session_id == session_id))
    records = result.scalars().all()
    return [
        RecordResponse(
            id=r.id,
            record_type=r.record_type,
            payload=decrypt_json(r.payload_encrypted),
            created_at=r.created_at,
        )
        for r in records
    ]


@router.delete("/{record_id}", status_code=204)
async def delete_record(
    record_id: str,
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> None:
    # Only the owner can delete — a record id alone used to be enough.
    result = await db.execute(
        select(SavedRecord)
        .join(ConversationSession, ConversationSession.id == SavedRecord.session_id)
        .where(SavedRecord.id == record_id, _owner_filter(user, device_id))
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    await db.delete(record)
    await db.commit()
