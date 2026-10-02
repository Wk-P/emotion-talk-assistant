"""Admin choice of the OpenAI model (see app/services/model_settings.py).
Anyone with admin access can see it; only a superadmin can change it, since
it affects every participant's conversation and the running cost."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required
from app.core.config import get_settings
from app.db.session import get_db
from app.models.app_setting import AppSetting
from app.models.enums import UserRole
from app.models.user import User
from app.services import model_settings

router = APIRouter(prefix="/api/admin/model", tags=["admin-model"])


class ModelCandidate(BaseModel):
    id: str
    released: str  # YYYY-MM-DD
    usable: bool
    error: str | None = None


class ModelOverview(BaseModel):
    current: str
    default: str  # OPENAI_MODEL from .env, used when nothing is chosen here
    chosen_here: bool
    updated_at: str | None
    updated_by: str | None
    candidates: list[ModelCandidate]
    checked_at: str
    recent_days: int


class SetModelRequest(BaseModel):
    # None = go back to the .env default.
    model: str | None = Field(default=None, max_length=100)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d")


async def _overview(db: AsyncSession, refresh: bool) -> ModelOverview:
    try:
        checks, checked_at = await model_settings.recent_chat_models(refresh=refresh)
    except Exception as e:  # listing itself failed (bad key, network)
        raise HTTPException(status_code=503, detail=f"could not list models: {type(e).__name__}") from e
    row = await model_settings.model_source(db)
    updated_by = None
    if row and row.updated_by_id:
        user = await db.get(User, row.updated_by_id)
        updated_by = user.username if user else None
    return ModelOverview(
        current=await model_settings.current_model(db),
        default=get_settings().openai_model,
        chosen_here=bool(row and row.value),
        updated_at=row.updated_at.isoformat() if row and row.updated_at else None,
        updated_by=updated_by,
        candidates=[ModelCandidate(id=c.id, released=_day(c.created), usable=c.usable, error=c.error) for c in checks],
        checked_at=datetime.fromtimestamp(checked_at, UTC).isoformat(),
        recent_days=model_settings.RECENT_DAYS,
    )


@router.get("", response_model=ModelOverview)
async def get_model(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> ModelOverview:
    return await _overview(db, refresh)


@router.put("", response_model=ModelOverview)
async def set_model(
    payload: SetModelRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> ModelOverview:
    if admin.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="superadmin access required")

    row = await db.get(AppSetting, model_settings.MODEL_KEY)
    if payload.model:
        # Never switch every conversation to a model that doesn't answer.
        ok, err = await model_settings.probe(payload.model)
        if not ok:
            raise HTTPException(status_code=422, detail=f"model not usable: {err}")
        if row is None:
            row = AppSetting(key=model_settings.MODEL_KEY, value=payload.model)
        row.value = payload.model
        row.updated_by_id = admin.id
        db.add(row)
    elif row is not None:
        await db.delete(row)
    await db.commit()
    return await _overview(db, refresh=False)


