"""Admin editing of the prompt blocks in app/prompts/registry.py. Open to
both ADMIN and SUPERADMIN — researchers tune the prompt text themselves
rather than going through a code change and redeploy."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required
from app.db.session import get_db
from app.models.enums import Language
from app.models.prompt import PromptVersion
from app.models.user import User
from app.prompts import registry
from app.prompts.router import build_prompt
from app.schemas.prompt import (
    PromptItem,
    PromptOverview,
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptSaveRequest,
    PromptVersionItem,
)
from app.services.llm import RESPONSE_INSTRUCTIONS, generate_turn

router = APIRouter(prefix="/api/admin/prompts", tags=["admin-prompts"])


def _check_key(key: str) -> None:
    if key not in registry.DEFAULTS:
        raise HTTPException(status_code=404, detail="unknown prompt key")


async def _usernames(db: AsyncSession, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    result = await db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
    return dict(result.all())


def _item(key: str, language: Language, row: PromptVersion | None, usernames: dict[str, str]) -> PromptItem:
    default = registry.DEFAULTS[key][language]
    return PromptItem(
        key=key,
        language=language,
        version=row.version if row else 0,
        content=row.content if row else default,
        default_content=default,
        updated_at=row.created_at.isoformat() if row else None,
        updated_by=usernames.get(row.created_by_id) if row and row.created_by_id else None,
    )


@router.get("", response_model=PromptOverview)
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> PromptOverview:
    keys = list(registry.DEFAULTS)
    latest = {lang: await registry.latest_versions(db, keys, lang) for lang in Language}
    usernames = await _usernames(db, {r.created_by_id for rows in latest.values() for r in rows.values() if r.created_by_id})
    return PromptOverview(
        items=[_item(key, lang, latest[lang].get(key), usernames) for key in keys for lang in Language],
        output_format=RESPONSE_INSTRUCTIONS.strip(),
    )


@router.get("/{key}/{language}/versions", response_model=list[PromptVersionItem])
async def list_versions(
    key: str,
    language: Language,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[PromptVersionItem]:
    _check_key(key)
    result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.key == key, PromptVersion.language == language)
        .order_by(PromptVersion.version.desc())
    )
    rows = result.scalars().all()
    usernames = await _usernames(db, {r.created_by_id for r in rows if r.created_by_id})
    return [
        PromptVersionItem(
            version=r.version,
            content=r.content,
            note=r.note,
            created_at=r.created_at.isoformat(),
            created_by=usernames.get(r.created_by_id) if r.created_by_id else None,
        )
        for r in rows
    ]


@router.post("/{key}/{language}", response_model=PromptItem)
async def save_prompt(
    key: str,
    language: Language,
    payload: PromptSaveRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> PromptItem:
    """Publishes a new version, in effect from the next chat turn. Rollback
    and reset-to-default go through here too, as a new version carrying the
    older text — nothing is ever overwritten."""

    _check_key(key)
    current = (await registry.resolve(db, [key], language))[key]
    if payload.content == current.content:
        raise HTTPException(status_code=400, detail="content unchanged")

    row = PromptVersion(
        key=key,
        language=language,
        version=current.version + 1,
        content=payload.content,
        note=(payload.note or "").strip() or None,
        created_by_id=admin.id,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        # Someone else saved this same block in the meantime.
        await db.rollback()
        raise HTTPException(status_code=409, detail="prompt was changed by someone else, reload and retry")
    await db.refresh(row)
    return _item(key, language, row, {admin.id: admin.username})


@router.post("/preview", response_model=PromptPreviewResponse)
async def preview_prompt(
    payload: PromptPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> PromptPreviewResponse:
    """Runs one model turn with draft text, without touching any real
    session or saving anything — lets an edit be tried before publishing."""

    for key, content in payload.overrides.items():
        _check_key(key)
        if not content or len(content) > registry.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=422, detail=f"invalid draft for {key}")

    system_prompt, versions = await build_prompt(
        db,
        payload.intent,
        payload.language,
        1.0 if payload.self_kindness else 0.0,
        overrides=payload.overrides,
    )
    response = await generate_turn(
        system_prompt,
        [m.model_dump() for m in payload.history],
        payload.message,
    )
    return PromptPreviewResponse(
        reply_text=response.reply_text,
        candidates=response.candidates,
        system_prompt=system_prompt + RESPONSE_INSTRUCTIONS,
        prompt_versions=versions,
    )
