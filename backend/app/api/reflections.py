"""每日省察 — the daily usage reflection questionnaire. See
app/models/reflection.py."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_required
from app.db.session import get_db
from app.models.reflection import DailyReflection
from app.models.user import User
from app.schemas.reflection import ReflectionAnswers, ReflectionItem, SaveReflectionRequest
from app.services.crypto import decrypt_json, encrypt_json

router = APIRouter(prefix="/api/reflections", tags=["reflections"])

DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _owner_filter(user: User) -> ColumnElement[bool]:
    return DailyReflection.user_id == user.id


def to_item(r: DailyReflection) -> ReflectionItem:
    return ReflectionItem(
        id=r.id,
        day=r.day,
        language=r.language,
        answers=ReflectionAnswers(**decrypt_json(r.answers_encrypted)),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=list[ReflectionItem])
async def list_my_reflections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> list[ReflectionItem]:
    result = await db.execute(
        select(DailyReflection).where(_owner_filter(user)).order_by(DailyReflection.day.desc())
    )
    return [to_item(r) for r in result.scalars().all()]


@router.put("/{day}", response_model=ReflectionItem)
async def save_reflection(
    payload: SaveReflectionRequest,
    day: str = Path(pattern=DAY_PATTERN),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> ReflectionItem:
    """Create or update the caller's reflection for `day` (their local date)."""

    try:
        date.fromisoformat(day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid date") from e
    answers = payload.answers.model_dump()
    if not any(v.strip() for v in answers.values()):
        raise HTTPException(status_code=400, detail="at least one answer is required")

    owner = _owner_filter(user)
    existing = (
        await db.execute(select(DailyReflection).where(owner, DailyReflection.day == day))
    ).scalar_one_or_none()
    if existing is None:
        existing = DailyReflection(user_id=user.id, day=day)
    existing.language = payload.language
    existing.answers_encrypted = encrypt_json(answers).decode("utf-8")
    db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return to_item(existing)


@router.delete("/{reflection_id}", status_code=204)
async def delete_reflection(
    reflection_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> None:
    row = (
        await db.execute(
            select(DailyReflection).where(DailyReflection.id == reflection_id, _owner_filter(user))
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="reflection not found")
    await db.delete(row)
    await db.commit()
