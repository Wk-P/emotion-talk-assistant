"""Which OpenAI model answers the chat, and how hard it thinks — both chosen
from the admin page.

The model set on the admin page (app_settings "openai_model") wins; without
one, OPENAI_MODEL from .env is used. Candidates offered on the admin page are
the chat models OpenAI released in the last year that actually work with this
site's call (a real JSON-mode request) — probed, not guessed from names alone.
Each also gets plain-language tags (model_tags) and a probe of whether it
accepts a reasoning effort.

The reasoning effort (app_settings "reasoning_effort": low/medium/high) is
sent with every call when set; unset means OpenAI's default for the model.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field

from openai import APIError, AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.app_setting import AppSetting

MODEL_KEY = "openai_model"
EFFORT_KEY = "reasoning_effort"
EFFORTS = ("low", "medium", "high")
RECENT_DAYS = 365  # "the last year"
CACHE_SECONDS = 6 * 3600

# Families that are never chat models (images, speech, embeddings, …).
_NOT_CHAT = re.compile(
    r"image|dall-e|sora|tts|whisper|transcri|audio|realtime|live|embedding|moderation|search|computer-use|codex",
    re.IGNORECASE,
)
# Left out of the list: dated snapshots (the undated name points at the same
# model) and "-pro" models (very slow and costly — unsuited to live chat).
_NOT_LISTED = re.compile(r"-\d{4}-\d{2}-\d{2}$|-pro\b", re.IGNORECASE)

# Tested on this project, per the project lead (2026-10-03). Overrides the
# name-based tags below.
_TESTED_TAGS: dict[str, list[str]] = {
    "gpt-5.6-sol": ["recommended", "tested_good"],
    "gpt-5.6-terra": ["tested_weak"],
}


def model_tags(model: str) -> list[str]:
    """Plain-language traits for the admin list; the frontend translates
    each tag. Only what the name reliably says, or what was tested here —
    nothing guessed."""

    if model in _TESTED_TAGS:
        return _TESTED_TAGS[model]
    if "-nano" in model:
        return ["tiny"]
    if "-mini" in model:
        return ["small"]
    if "chat-latest" in model:
        return ["chat_latest"]
    if re.fullmatch(r"gpt-\d+(\.\d+)?", model):
        return ["full"]
    return ["untested"]


async def current_model(db: AsyncSession) -> str:
    row = await db.get(AppSetting, MODEL_KEY)
    return row.value if row and row.value else get_settings().openai_model


async def model_source(db: AsyncSession) -> AppSetting | None:
    return await db.get(AppSetting, MODEL_KEY)


async def current_effort(db: AsyncSession) -> str | None:
    row = await db.get(AppSetting, EFFORT_KEY)
    return row.value if row and row.value in EFFORTS else None


@dataclass
class ModelCheck:
    id: str
    created: int  # unix seconds, from OpenAI
    usable: bool
    error: str | None = None
    supports_effort: bool = False
    tags: list[str] = field(default_factory=list)


async def probe(model: str, effort: str | None = None) -> tuple[bool, str | None]:
    """One tiny request shaped like a real chat turn (JSON mode), with the
    given reasoning effort if any."""

    client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    try:
        await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": 'Reply with the JSON object {"ok": true}.'},
                {"role": "user", "content": "ping"},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=200,
            **({"reasoning_effort": effort} if effort else {}),
        )
        return True, None
    except APIError as e:
        status = getattr(e, "status_code", None)
        return False, f"{type(e).__name__}{f' {status}' if status else ''}"


_cache: tuple[float, list[ModelCheck]] | None = None
_lock = asyncio.Lock()


async def recent_chat_models(refresh: bool = False) -> tuple[list[ModelCheck], float]:
    """Recent chat models with a usability check each; cached for a few
    hours so opening the admin page doesn't call OpenAI every time."""

    global _cache
    async with _lock:
        if _cache and not refresh and time.time() - _cache[0] < CACHE_SECONDS:
            return _cache[1], _cache[0]

        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        cutoff = time.time() - RECENT_DAYS * 86400
        listed = [
            m
            for m in (await client.models.list()).data
            if m.created >= cutoff and not _NOT_CHAT.search(m.id) and not _NOT_LISTED.search(m.id)
        ]
        sem = asyncio.Semaphore(4)

        async def check(m) -> ModelCheck:
            async with sem:
                ok, err = await probe(m.id)
                effort_ok = (await probe(m.id, "low"))[0] if ok else False
            return ModelCheck(
                id=m.id, created=m.created, usable=ok, error=err, supports_effort=effort_ok, tags=model_tags(m.id)
            )

        # Still listed by OpenAI but retired (404 on use): nothing to choose.
        checks = sorted(
            (c for c in await asyncio.gather(*(check(m) for m in listed)) if c.error != "NotFoundError 404"),
            key=lambda c: -c.created,
        )
        _cache = (time.time(), checks)
        return checks, _cache[0]
