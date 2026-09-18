from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import ConsentCategory
from app.models.record import SavedRecord
from app.models.session import ConversationSession
from app.schemas.record import RecordResponse, SaveRecordRequest
from app.services.crypto import decrypt_json, encrypt_json

router = APIRouter(prefix="/api/records", tags=["records"])

# Records saved from a self-kindness/self-encouragement/value-goal/recovery-plan
# card fall under EMOTION_RECORDS consent unless they concern acculturation
# problem-type tagging, which is CULTURE_ADAPTATION_INFO instead.
_CULTURE_TAGGED_TYPES = {"cause_interpretation"}


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
async def delete_record(record_id: str, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(SavedRecord).where(SavedRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    await db.delete(record)
    await db.commit()
