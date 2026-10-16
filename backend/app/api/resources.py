import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required
from app.core.timefmt import kst_iso
from app.db.session import get_db
from app.models.enums import Language
from app.models.resource import CrisisResource
from app.models.user import User

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("")
async def list_resources(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Help/resources screen (always-on entry point, design principle 8.1).
    Returns only verified rows from CrisisResource — never AI-generated."""

    result = await db.execute(select(CrisisResource))
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "country": r.country,
            "category": r.category,
            "name": r.name,
            "description": r.description,
            "contact": r.contact,
            "url": r.url,
            "verified_at": kst_iso(r.verified_at),
        }
        for r in rows
    ]


# ---- Admin: the resource directory itself (admin page "危机求助资源") ----
# Admins enter only contacts they have verified themselves; `verified_at` is
# the date of that check and is shown to users next to the contact.

admin_router = APIRouter(prefix="/api/admin/resources", tags=["admin-resources"])


class ResourcePayload(BaseModel):
    country: str = Field(min_length=1, max_length=8)
    category: str = Field(default="other", max_length=64)
    # By language value ("zh"/"ko").
    name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    contact: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    # YYYY-MM-DD
    verified_at: date


def _apply(row: CrisisResource, payload: ResourcePayload) -> None:
    langs = {lang.value for lang in Language}
    name = {k: v.strip() for k, v in payload.name.items() if k in langs and v.strip()}
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    row.country = payload.country.strip().upper()
    row.category = payload.category.strip() or "other"
    row.name = name
    row.description = {k: v.strip() for k, v in payload.description.items() if k in langs}
    row.contact = payload.contact.strip()
    row.url = (payload.url or "").strip() or None
    row.verified_at = datetime.combine(payload.verified_at, time(), tzinfo=timezone.utc)


@admin_router.get("")
async def admin_list_resources(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin_required)
) -> list[dict]:
    return await list_resources(db)


@admin_router.post("", status_code=201)
async def create_resource(
    payload: ResourcePayload, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin_required)
) -> dict:
    row = CrisisResource(id=f"custom-{uuid.uuid4().hex[:12]}")
    _apply(row, payload)
    db.add(row)
    await db.commit()
    return {"id": row.id}


@admin_router.put("/{resource_id}")
async def update_resource(
    resource_id: str,
    payload: ResourcePayload,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> dict:
    row = await db.get(CrisisResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    _apply(row, payload)
    await db.commit()
    return {"id": row.id}


@admin_router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin_required)
) -> Response:
    row = await db.get(CrisisResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
