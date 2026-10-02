"""Which OpenAI model answers the chat, chosen from the admin page.

The model set on the admin page (app_settings "openai_model") wins; without
one, OPENAI_MODEL from .env is used. Candidates offered on the admin page are
the models OpenAI released in the last ~3 months that are chat models and
actually work with this site's call (a real JSON-mode request) — probed, not
guessed from names alone.
"""

import asyncio
import re
import time
from dataclasses import dataclass

from openai import APIError, AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.app_setting import AppSetting

MODEL_KEY = "openai_model"
RECENT_DAYS = 92  # "the last 3 months"
CACHE_SECONDS = 6 * 3600

# Families that are never chat models (images, speech, embeddings, …).
_NOT_CHAT = re.compile(
    r"image|dall-e|sora|tts|whisper|transcri|audio|realtime|live|embedding|moderation|search|computer-use|codex",
    re.IGNORECASE,
)


async def current_model(db: AsyncSession) -> str:
    row = await db.get(AppSetting, MODEL_KEY)
    return row.value if row and row.value else get_settings().openai_model


async def model_source(db: AsyncSession) -> AppSetting | None:
    return await db.get(AppSetting, MODEL_KEY)


@dataclass
class ModelCheck:
    id: str
    created: int  # unix seconds, from OpenAI
    usable: bool
    error: str | None = None


async def probe(model: str) -> tuple[bool, str | None]:
    """One tiny request shaped like a real chat turn (JSON mode)."""

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
        listed = [m for m in (await client.models.list()).data if m.created >= cutoff and not _NOT_CHAT.search(m.id)]
        sem = asyncio.Semaphore(4)

        async def check(m) -> ModelCheck:
            async with sem:
                ok, err = await probe(m.id)
            return ModelCheck(id=m.id, created=m.created, usable=ok, error=err)

        checks = sorted(await asyncio.gather(*(check(m) for m in listed)), key=lambda c: -c.created)
        _cache = (time.time(), checks)
        return checks, _cache[0]
