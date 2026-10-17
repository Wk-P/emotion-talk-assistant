"""Advanced AI settings (app/services/ai_params.py): view, save, and ask the
model in use to recommend values. Any admin can use them."""

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required
from app.db.session import get_db
from app.models.user import User
from app.services import ai_params
from app.services.llm import LLMUnavailable, _complete_json
from app.services.model_settings import current_effort, current_model

router = APIRouter(prefix="/api/admin/ai-params", tags=["admin-ai-params"])


class FieldRange(BaseModel):
    min: float
    max: float
    integer: bool
    required: bool


class AiParamsOverview(BaseModel):
    values: dict[str, float | None]
    defaults: dict[str, float | None]
    ranges: dict[str, FieldRange]
    model: str
    effort: str | None


class Recommendation(BaseModel):
    values: dict[str, float | None]
    # Why, per field, in the admin's language.
    reasons: dict[str, str]
    # False: the AI call failed and the built-in values are shown instead.
    from_ai: bool


class RecommendRequest(BaseModel):
    language: Literal["zh", "ko", "en"] = "zh"


async def _overview(db: AsyncSession) -> AiParamsOverview:
    return AiParamsOverview(
        values=await ai_params.load(db),
        defaults=ai_params.defaults(),
        ranges={
            k: FieldRange(min=lo, max=hi, integer=is_int, required=k in ai_params.REQUIRED)
            for k, (lo, hi, is_int, _) in ai_params.FIELDS.items()
        },
        model=await current_model(db),
        effort=await current_effort(db),
    )


@router.get("", response_model=AiParamsOverview)
async def get_params(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin_required)
) -> AiParamsOverview:
    return await _overview(db)


@router.put("", response_model=AiParamsOverview)
async def set_params(
    payload: dict[str, float | None],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> AiParamsOverview:
    # Out-of-range values are fitted, not refused (ai_params.clean).
    await ai_params.save(db, payload, admin.id)
    await db.commit()
    return await _overview(db)


_LANG_NAMES = {"zh": "简体中文", "ko": "한국어", "en": "English"}

_RECOMMEND_PROMPT = """You tune the request parameters of an emotional-support chat app.
Users talk through a feeling in a guided flow (listen, explore, self-check,
self-kindness, small action, closing); conversations often run 20-40 turns.
Replies must be warm, steady, consistent and safe, and remember what the user
said earlier. Each reply is a JSON object (reply text plus a few signals).

Model in use: {model}. Reasoning effort: {effort}.
Current settings: {current}
Parameters (null = not sent, the model's own default applies):
{fields}

Notes: reasoning models (e.g. gpt-5 family, o-series) usually reject or ignore
temperature, top_p and the penalties - recommend null for those then.
max_tokens includes reasoning tokens on reasoning models, so keep it generous
or null. history_turns is how many recent messages the model sees.

Answer with a JSON object: {{"values": {{<every parameter>: number or null}},
"reasons": {{<every parameter>: one short plain sentence in {lang}, no jargon,
for a non-technical admin}}}}"""


@router.post("/recommend", response_model=Recommendation)
async def recommend(
    payload: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> Recommendation:
    model, effort = await current_model(db), await current_effort(db)
    fields = "\n".join(
        f"- {k}: {lo}-{hi}{' integer' if is_int else ''}{', required' if k in ai_params.REQUIRED else ''}"
        for k, (lo, hi, is_int, _) in ai_params.FIELDS.items()
    )
    prompt = _RECOMMEND_PROMPT.format(
        model=model,
        effort=effort or "model default",
        current=json.dumps(await ai_params.load(db)),
        fields=fields,
        lang=_LANG_NAMES[payload.language],
    )
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": "Recommend."}]
    try:
        parsed: Any = await _complete_json(messages, model, effort)
    except LLMUnavailable:
        parsed = None
    values = parsed.get("values") if isinstance(parsed, dict) else None
    if not isinstance(values, dict):
        return Recommendation(
            values=dict(ai_params.FALLBACK_RECOMMENDED), reasons={}, from_ai=False
        )
    reasons = parsed.get("reasons") if isinstance(parsed.get("reasons"), dict) else {}
    return Recommendation(
        values={k: ai_params.clean(k, values.get(k)) for k in ai_params.FIELDS},
        reasons={k: str(reasons[k])[:300] for k in ai_params.FIELDS if reasons.get(k)},
        from_ai=True,
    )
