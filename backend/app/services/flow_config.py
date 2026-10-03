"""The flow settings admins control from the admin page ("对话流程顺序"), beyond
the step order and wording:

  - per step, the minimum user turns before the model's "this step is done"
    is accepted, and the maximum after which the step moves on regardless;
  - the purpose buttons shown in the purpose step: their wording (zh/ko)
    and which later step each one jumps to (or none: the next step);
  - how many recent messages the model sees each turn.

Stored as one JSON object in app_settings ("flow_config"); anything missing
falls back to the defaults below, which follow the project lead's prompt
(documents/02_内容与需求/对话运行Prompt_负责人.md).
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.enums import Language
from app.prompts import registry, stages

SETTING_KEY = "flow_config"

# Steps that end on something the user does: no minimum (listen, self_check
# still have a maximum), or no limits at all (purpose, closing, and the
# one-turn stabilization / ending replies).
NO_MIN = {stages.LISTEN, stages.SELF_CHECK, stages.PURPOSE, stages.CLOSING}
NO_LIMITS = {stages.PURPOSE, stages.CLOSING, stages.STABILIZATION, stages.ENDING}

DEFAULT_LIMITS: dict[str, tuple[int, int]] = {
    stages.LISTEN: (1, 10),
    stages.EXPLORE: (3, 12),
    stages.SELF_CHECK: (1, 3),
    stages.SELF_KINDNESS: (2, 8),
}
DEFAULT_MIN, DEFAULT_MAX = 1, 8
MAX_TURNS_CAP = 50

DEFAULT_PURPOSES: list[dict[str, Any]] = [
    {"id": "vent", "labels": {"zh": "我只是想说一说", "ko": "그냥 이야기하고 싶어요"}, "jump": None},
    {"id": "emotions", "labels": {"zh": "我想整理自己的情绪", "ko": "내 감정을 정리하고 싶어요"}, "jump": None},
    {
        "id": "why",
        "labels": {"zh": "我想理解为什么这件事让我这么难受", "ko": "이 일이 왜 이렇게 힘든지 이해하고 싶어요"},
        "jump": None,
    },
    {"id": "calm", "labels": {"zh": "我想先让自己平静一点", "ko": "우선 마음을 좀 가라앉히고 싶어요"}, "jump": stages.REGULATE},
    {"id": "plan", "labels": {"zh": "我想一起想想接下来怎么办", "ko": "앞으로 어떻게 할지 함께 생각해 보고 싶어요"}, "jump": stages.ACT},
]
MAX_PURPOSES = 8

DEFAULT_HISTORY = 12
HISTORY_RANGE = (2, 60)


@dataclass
class FlowConfig:
    # Active steps in order, ending with closing (registry.active_flow_order).
    order: list[str]
    limits: dict[str, tuple[int, int]] = field(default_factory=dict)
    purposes: list[dict[str, Any]] = field(default_factory=lambda: [dict(p) for p in DEFAULT_PURPOSES])
    history_turns: int = DEFAULT_HISTORY

    def limits_for(self, stage: str) -> tuple[int, int]:
        return self.limits.get(stage) or DEFAULT_LIMITS.get(stage, (DEFAULT_MIN, DEFAULT_MAX))

    def purpose_label(self, pid: str, language: Language) -> str | None:
        p = next((p for p in self.purposes if p["id"] == pid), None)
        return (p["labels"].get(language.value) or next(iter(p["labels"].values()), "")) if p else None


async def _saved(db: AsyncSession) -> dict[str, Any]:
    row = await db.get(AppSetting, SETTING_KEY)
    try:
        value = json.loads(row.value) if row and row.value else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _limits_from(saved: dict[str, Any]) -> dict[str, tuple[int, int]]:
    out = {}
    for key, v in (saved.get("limits") or {}).items():
        if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(n, int) for n in v):
            out[key] = (v[0], v[1])
    return out


async def load(db: AsyncSession) -> FlowConfig:
    saved = await _saved(db)
    return FlowConfig(
        order=await registry.active_flow_order(db),
        limits=_limits_from(saved),
        purposes=saved.get("purposes") or [dict(p) for p in DEFAULT_PURPOSES],
        history_turns=saved.get("history_turns") or DEFAULT_HISTORY,
    )


async def for_admin(db: AsyncSession) -> dict[str, Any]:
    """Everything the admin page edits, with defaults filled in."""

    saved = await _saved(db)
    limits = _limits_from(saved)
    steps = [m.key for m in await registry.load_modules(db) if m.is_stage and m.key not in NO_LIMITS]
    return {
        "limits": {k: list(limits.get(k) or DEFAULT_LIMITS.get(k, (DEFAULT_MIN, DEFAULT_MAX))) for k in steps},
        "purposes": saved.get("purposes") or DEFAULT_PURPOSES,
        "history_turns": saved.get("history_turns") or DEFAULT_HISTORY,
        "defaults": {
            "limits": {k: list(DEFAULT_LIMITS.get(k, (DEFAULT_MIN, DEFAULT_MAX))) for k in steps},
            "purposes": DEFAULT_PURPOSES,
            "history_turns": DEFAULT_HISTORY,
        },
    }


def validate(payload: dict[str, Any], stage_keys: set[str]) -> str | None:
    """None if valid, else a short reason."""

    for key, (low, high) in payload["limits"].items():
        if key not in stage_keys or key in NO_LIMITS:
            return f"unknown step {key}"
        if not (1 <= low <= high <= MAX_TURNS_CAP):
            return f"bad limits for {key}"
    purposes = payload["purposes"]
    if not 1 <= len(purposes) <= MAX_PURPOSES:
        return "purposes count"
    ids = set()
    for p in purposes:
        if p["id"] in ids:
            return "duplicate purpose id"
        ids.add(p["id"])
        if not any((p["labels"].get(lang.value) or "").strip() for lang in Language):
            return "purpose label required"
        if p.get("jump") and p["jump"] not in stage_keys:
            return "unknown jump step"
    if not HISTORY_RANGE[0] <= payload["history_turns"] <= HISTORY_RANGE[1]:
        return "history_turns out of range"
    return None


async def save(db: AsyncSession, payload: dict[str, Any], admin_id: str | None) -> None:
    row = await db.get(AppSetting, SETTING_KEY)
    if row is None:
        row = AppSetting(key=SETTING_KEY, value="")
    row.value = json.dumps(
        {
            "limits": {k: list(v) for k, v in payload["limits"].items()},
            "purposes": payload["purposes"],
            "history_turns": payload["history_turns"],
        },
        ensure_ascii=False,
    )
    row.updated_by_id = admin_id
    db.add(row)
