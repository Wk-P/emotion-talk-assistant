"""Admin editing of the prompt blocks in app/prompts/registry.py. Open to
both ADMIN and SUPERADMIN — researchers tune the prompt text themselves
rather than going through a code change and redeploy. Besides editing text,
admins can rename and disable any block, and add (and delete) their own."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import kst_iso
from app.api.deps import get_current_admin_required
from app.db.session import get_db
from app.models.enums import Language
from app.models.prompt import PromptModule, PromptVersion
from app.models.user import User
from app.prompts import registry
from app.prompts.router import build_prompt
from app.schemas.prompt import (
    FlowConfigOverview,
    FlowConfigPayload,
    FlowOrder,
    PromptItem,
    PromptModuleCreateRequest,
    PromptModuleItem,
    PromptModuleUpdateRequest,
    PromptOverview,
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptSaveRequest,
    PromptVersionItem,
)
from app.services import flow_config
from app.services.llm import LLMUnavailable, generate_turn
from app.services.model_settings import current_effort, current_model

router = APIRouter(prefix="/api/admin/prompts", tags=["admin-prompts"])


async def _check_key(db: AsyncSession, key: str) -> None:
    if key in registry.DEFAULTS:
        return
    if key.startswith(registry.CUSTOM_PREFIX) and await db.get(PromptModule, key):
        return
    raise HTTPException(status_code=404, detail="unknown prompt key")


def _module_item(m: registry.Module) -> PromptModuleItem:
    return PromptModuleItem(
        key=m.key,
        group=m.group,
        built_in=m.built_in,
        enabled=m.enabled,
        names=m.names,
        flow_key=m.flow_key,
        is_stage=m.is_stage,
    )


async def _usernames(db: AsyncSession, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    result = await db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
    return dict(result.all())


def _item(key: str, language: Language, row: PromptVersion | None, usernames: dict[str, str]) -> PromptItem:
    default = registry.default_content(key, language)
    return PromptItem(
        key=key,
        language=language,
        version=row.version if row else 0,
        content=row.content if row else default,
        default_content=default,
        updated_at=kst_iso(row.created_at) if row else None,
        updated_by=usernames.get(row.created_by_id) if row and row.created_by_id else None,
    )


@router.get("", response_model=PromptOverview)
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> PromptOverview:
    modules = await registry.load_modules(db)
    keys = [m.key for m in modules]
    latest = {lang: await registry.latest_versions(db, keys, lang) for lang in Language}
    usernames = await _usernames(db, {r.created_by_id for rows in latest.values() for r in rows.values() if r.created_by_id})
    return PromptOverview(
        items=[_item(key, lang, latest[lang].get(key), usernames) for key in keys for lang in Language],
        modules=[_module_item(m) for m in modules],
        output_format=registry.default_content("system.output_json", Language.ZH),
    )


@router.get("/flow-order", response_model=FlowOrder)
async def get_flow_order(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> FlowOrder:
    return FlowOrder(order=registry.flow_sequence(await registry.load_modules(db)))


@router.put("/flow-order", response_model=FlowOrder)
async def set_flow_order(
    payload: FlowOrder,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> FlowOrder:
    """Saves the order of the steps. Must list every orderable step exactly
    once; conversations follow it from their next turn on (app/services/flow.py)."""

    current = registry.flow_sequence(await registry.load_modules(db))
    if sorted(payload.order) != sorted(current):
        raise HTTPException(status_code=422, detail="order must list every step exactly once")
    await registry.save_flow_order(db, payload.order, admin.id)
    await db.commit()
    return FlowOrder(order=payload.order)


@router.get("/flow-config", response_model=FlowConfigOverview)
async def get_flow_config(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> FlowConfigOverview:
    return FlowConfigOverview(**await flow_config.for_admin(db))


@router.put("/flow-config", response_model=FlowConfigOverview)
async def set_flow_config(
    payload: FlowConfigPayload,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> FlowConfigOverview:
    """Saves the per-step turn limits, the purpose buttons and the history
    length. Conversations use them from their next turn on."""

    data = payload.model_dump()
    data["purposes"] = [
        {**p, "labels": {k: v.strip() for k, v in p["labels"].items() if k in {lang.value for lang in Language}}}
        for p in data["purposes"]
    ]
    stage_keys = {m.key for m in await registry.load_modules(db) if m.is_stage}
    reason = flow_config.validate(data, stage_keys)
    if reason:
        raise HTTPException(status_code=422, detail=reason)
    await flow_config.save(db, data, admin.id)
    await db.commit()
    return FlowConfigOverview(**await flow_config.for_admin(db))


@router.post("/modules", response_model=PromptModuleItem)
async def create_module(
    payload: PromptModuleCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> PromptModuleItem:
    """Adds an empty block to a group. Its text is then written and saved
    like any other block's; until then it is empty and so not sent."""

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    flow_key = None
    if payload.group == "flow" and payload.flow_key:
        # A block attached to a step; without flow_key it is a step of its own,
        # placed last (before closing) until admins move it.
        stage_keys = {m.key for m in await registry.load_modules(db) if m.is_stage}
        if payload.flow_key not in stage_keys:
            raise HTTPException(status_code=422, detail="flow_key must be a stage")
        flow_key = payload.flow_key
    row = PromptModule(
        key=f"{registry.CUSTOM_PREFIX}{uuid.uuid4().hex[:12]}",
        group=payload.group,
        flow_key=flow_key,
        # Same name for both languages until someone renames one.
        names={lang.value: name for lang in Language},
        enabled=True,
        created_by_id=admin.id,
    )
    db.add(row)
    await db.commit()
    return PromptModuleItem(
        key=row.key,
        group=row.group,
        built_in=False,
        enabled=True,
        names=row.names,
        flow_key=flow_key,
        is_stage=row.group == "flow" and not flow_key,
    )


@router.patch("/modules/{key}", response_model=PromptModuleItem)
async def update_module(
    key: str,
    payload: PromptModuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> PromptModuleItem:
    """Renames (per language) and/or enables/disables a block, built-in or
    added. A built-in block gets its settings row on first change."""

    await _check_key(db, key)
    row = await db.get(PromptModule, key)
    if row is None:  # built-in, never changed before
        group = "rules" if key in registry.RULE_KEYS else "system" if key in registry.DEFAULTS and key.startswith("system.") else "flow"
        row = PromptModule(key=key, group=group, names={}, enabled=registry.default_enabled(key))
        db.add(row)

    if payload.name is not None:
        if payload.language is None:
            raise HTTPException(status_code=422, detail="language required to rename")
        name = payload.name.strip()
        names = dict(row.names or {})
        if name:
            names[payload.language.value] = name
        elif key.startswith(registry.CUSTOM_PREFIX) and not any(
            v.strip() for k, v in names.items() if k != payload.language.value
        ):
            # An added block has no default name to fall back to.
            raise HTTPException(status_code=422, detail="name required")
        else:
            names.pop(payload.language.value, None)
        row.names = names
    if payload.enabled is not None:
        row.enabled = payload.enabled

    await db.commit()
    return PromptModuleItem(
        key=row.key,
        group=row.group,
        built_in=not row.key.startswith(registry.CUSTOM_PREFIX),
        enabled=row.enabled,
        names=row.names or {},
        flow_key=row.flow_key,
    )


@router.delete("/modules/{key}", status_code=204)
async def delete_module(
    key: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> Response:
    """Only admin-added blocks can be deleted (built-in ones can be disabled
    instead). Their saved text versions are kept, so past messages'
    prompt_versions still point at real text for research analysis."""

    if not key.startswith(registry.CUSTOM_PREFIX):
        raise HTTPException(status_code=400, detail="built-in blocks can only be disabled")
    row = await db.get(PromptModule, key)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown prompt key")
    if row.group == "flow" and not row.flow_key:
        # A step of its own: blocks attached to it would be left pointing at nothing.
        attached = await db.execute(select(PromptModule.key).where(PromptModule.flow_key == key).limit(1))
        if attached.first():
            raise HTTPException(status_code=409, detail="step still has blocks attached")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.get("/{key}/{language}/versions", response_model=list[PromptVersionItem])
async def list_versions(
    key: str,
    language: Language,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[PromptVersionItem]:
    await _check_key(db, key)
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
            created_at=kst_iso(r.created_at),
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

    await _check_key(db, key)
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
        await _check_key(db, key)
        if not content or len(content) > registry.MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=422, detail=f"invalid draft for {key}")

    if payload.stage not in {m.key for m in await registry.load_modules(db) if m.is_stage}:
        raise HTTPException(status_code=422, detail="stage must be one of the built-in stages")
    system_prompt, versions = await build_prompt(db, payload.stage, payload.language, overrides=payload.overrides)
    try:
        response = await generate_turn(
            system_prompt,
            [m.model_dump() for m in payload.history],
            payload.message,
            await current_model(db),
            effort=await current_effort(db),
        )
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e
    return PromptPreviewResponse(
        reply_text=response.reply_text,
        candidates=response.candidates,
        system_prompt=system_prompt,
        prompt_versions=versions,
    )
