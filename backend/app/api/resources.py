from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.resource import CrisisResource

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
            "verified_at": r.verified_at.isoformat(),
        }
        for r in rows
    ]
