"""Advanced AI settings, admin-set on the "高级设置" page: how many recent
messages the model sees, and the sampling / length / connection parameters
sent with every chat call.

Stored as one JSON object in app_settings ("ai_params"). A value of None
means "not sent": the model's own default applies. Models that reject a
parameter (reasoning models often refuse temperature, top_p, penalties) get
it dropped automatically, see app/services/llm.py.
"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

SETTING_KEY = "ai_params"
# history_turns used to live in flow_config; read from there until saved here.
LEGACY_KEY = "flow_config"

# name: (min, max, is_int, default). None default = not sent.
FIELDS: dict[str, tuple[float, float, bool, float | None]] = {
    "history_turns": (2, 60, True, 12),
    "temperature": (0, 2, False, None),
    "top_p": (0, 1, False, None),
    "max_tokens": (200, 8000, True, None),
    "presence_penalty": (-2, 2, False, None),
    "frequency_penalty": (-2, 2, False, None),
    "timeout_seconds": (10, 300, True, 60),
    "max_retries": (0, 5, True, 2),
}
# Always needed, never "not sent".
REQUIRED = {"history_turns", "timeout_seconds", "max_retries"}
# Sent to OpenAI as chat.completions arguments (name there).
REQUEST_ARGS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_tokens": "max_completion_tokens",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
}

# Used when the AI recommendation fails: safe for a warm, steady
# emotional-support chat on any model.
FALLBACK_RECOMMENDED: dict[str, Any] = {
    "history_turns": 30,
    "temperature": None,
    "top_p": None,
    "max_tokens": 4000,
    "presence_penalty": None,
    "frequency_penalty": None,
    "timeout_seconds": 90,
    "max_retries": 2,
}


def defaults() -> dict[str, Any]:
    return {k: f[3] for k, f in FIELDS.items()}


def clean(name: str, value: Any) -> Any:
    """`value` fitted to the field's range and type; None if not given
    (or the default, for a required field)."""

    low, high, is_int, default = FIELDS[name]
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return default if name in REQUIRED else None
    value = min(max(value, low), high)
    return int(round(value)) if is_int else round(float(value), 2)


async def _json(db: AsyncSession, key: str) -> dict[str, Any]:
    row = await db.get(AppSetting, key)
    try:
        value = json.loads(row.value) if row and row.value else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


async def load(db: AsyncSession) -> dict[str, Any]:
    saved = await _json(db, SETTING_KEY)
    if "history_turns" not in saved:
        saved["history_turns"] = (await _json(db, LEGACY_KEY)).get("history_turns")
    return {k: clean(k, saved.get(k)) for k in FIELDS}


async def save(db: AsyncSession, values: dict[str, Any], admin_id: str | None) -> None:
    row = await db.get(AppSetting, SETTING_KEY) or AppSetting(key=SETTING_KEY, value="")
    row.value = json.dumps({k: clean(k, values.get(k)) for k in FIELDS})
    row.updated_by_id = admin_id
    db.add(row)


def request_args(params: dict[str, Any] | None) -> dict[str, Any]:
    """The chat.completions arguments to send (unset ones left out)."""

    params = params or {}
    return {arg: params[k] for k, arg in REQUEST_ARGS.items() if params.get(k) is not None}
