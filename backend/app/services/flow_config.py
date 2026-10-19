"""The flow settings admins control from the admin page ("对话流程顺序"), beyond
the step order and wording:

  - per step, the minimum user turns before the model's "this step is done"
    is accepted, and the maximum after which the step moves on regardless;
  - how many recent messages the model sees each turn;
  - the rules that used to be fixed in code: the shorter turn limits of
    self_kindness when self-criticism is weak, the crisis / "overwhelmed" /
    self-criticism word lists, how self-criticism is scored, where "tell me
    what to do" / "that's enough for today" lead, and the crisis reply text
    and resources shown.

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
from app.services import ai_params

SETTING_KEY = "flow_config"

# Purpose ends on the user's answer: no turn limits. (The closing step and
# the trigger-only steps ignore theirs too, see app/services/flow.py.)
NO_LIMITS = {stages.PURPOSE}

# Special roles, admin-set (None = no step has the role).
ROLE_KEYS = ("closing_step", "stabilize_step", "ending_step")
DEFAULT_ROLES = {"closing_step": stages.CLOSING, "stabilize_step": stages.STABILIZATION, "ending_step": stages.ENDING}
DEFAULT_SAFETY = [stages.CLOSING, stages.STABILIZATION, stages.ENDING]

DEFAULT_LIMITS: dict[str, tuple[int, int]] = {
    stages.LISTEN: (1, 10),
    stages.EXPLORE: (3, 12),
    stages.SELF_CHECK: (1, 3),
    stages.SELF_KINDNESS: (2, 8),
}
DEFAULT_MIN, DEFAULT_MAX = 1, 8
MAX_TURNS_CAP = 50

DEFAULT_HISTORY = 12
HISTORY_RANGE = (2, 60)

DEFAULT_WEAK_KINDNESS = (1, 2)

KEYWORD_LISTS = ("crisis", "watch", "self_criticism")
MAX_KEYWORDS, MAX_KEYWORD_LENGTH = 200, 40
DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "crisis": [
        "不想活", "自杀", "想死", "结束生命", "伤害自己", "割腕", "想杀", "杀了他", "杀了她",
        "죽고 싶", "자살", "자해", "삶을 끝", "죽이고 싶", "살고 싶지 않",
    ],
    "watch": ["撑不下去", "崩溃", "绝望", "没有意义了", "버틸 수 없", "무너질 것 같", "희망이 없", "의미가 없"],
    "self_criticism": [
        "我很没用", "我真差", "都怪我", "我不够好", "我很失败", "我什么都做不好",
        "나는 쓸모없", "내 잘못", "나는 부족", "나는 실패자", "나 때문",
    ],
}
DEFAULT_CRISIS_REPLY = {
    "zh": (
        "谢谢你愿意告诉我这些。这听起来很沉重，我想先确认一下你现在的安全状态——"
        "这部分超出了我能提供的支持范围，下面是一些经过核实的、可以立即联系的资源。"
    ),
    "ko": (
        "이렇게 말씀해 주셔서 고마워요. 지금 많이 힘드신 것 같아요. 먼저 지금 안전한 상태인지 확인하고 싶어요—"
        "이 부분은 제가 도울 수 있는 범위를 넘어서서, 지금 바로 연락할 수 있는 검증된 자원을 안내해 드릴게요."
    ),
}
MAX_CRISIS_REPLY = 1000

# Self-criticism level, 0-100: each message with a self-criticism word adds
# `up`, each without takes off `down`; at `strong` or more it counts as strong.
DEFAULT_CRITICISM = {"up": 25, "down": 5, "strong": 50}
# "Tell me what to do": the step it jumps to (None = ignored).
DEFAULT_TO_ACTION = stages.ACT
# Crisis resources shown: this country's ("" = all).
DEFAULT_CRISIS_COUNTRY = "KR"


@dataclass
class FlowConfig:
    # Active steps in order (registry.active_flow_order).
    order: list[str]
    limits: dict[str, tuple[int, int]] = field(default_factory=dict)
    history_turns: int = DEFAULT_HISTORY
    weak_kindness: tuple[int, int] = DEFAULT_WEAK_KINDNESS
    keywords: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_KEYWORDS.items()})
    crisis_reply: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CRISIS_REPLY))
    criticism: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CRITICISM))
    to_action_step: str | None = DEFAULT_TO_ACTION
    # Steps where "tell me what to do" is not acted on (e.g. a step that
    # itself asks what help the user wants).
    to_action_skip: list[str] = field(default_factory=list)
    # Jump only when the model reports the request two turns running: the
    # first time the next reply is told to check with the user.
    to_action_confirm: bool = True
    end_today_enabled: bool = True
    # Steps admins turned off.
    disabled: set[str] = field(default_factory=set)
    crisis_country: str = DEFAULT_CRISIS_COUNTRY
    closing_step: str | None = stages.CLOSING
    stabilize_step: str | None = stages.STABILIZATION
    ending_step: str | None = stages.ENDING
    safety_steps: list[str] = field(default_factory=lambda: list(DEFAULT_SAFETY))

    def usable(self, key: str | None) -> str | None:
        """`key` if it names a step that is on, else None."""
        return key if key and key not in self.disabled else None

    def crisis_text(self, language: Language) -> str:
        return (self.crisis_reply.get(language.value) or "").strip() or DEFAULT_CRISIS_REPLY[language.value]

    def limits_for(self, stage: str) -> tuple[int, int]:
        return self.limits.get(stage) or DEFAULT_LIMITS.get(stage, (DEFAULT_MIN, DEFAULT_MAX))


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


def _rules_from(saved: dict[str, Any]) -> dict[str, Any]:
    """The code-rule settings, defaults filled in. A keyword list saved empty
    stays empty (admins may turn a list off); one never saved is the default."""

    weak = saved.get("weak_kindness")
    keywords = dict(saved["keywords"]) if isinstance(saved.get("keywords"), dict) else {}
    if "crisis" not in keywords and keywords.get("crisis_extra"):
        # Saved when the built-in crisis words were fixed and only extras were set.
        keywords["crisis"] = [*DEFAULT_KEYWORDS["crisis"], *keywords["crisis_extra"]]
    return {
        "criticism": {**DEFAULT_CRITICISM, **(saved.get("criticism") or {})},
        "to_action_step": saved["to_action_step"] if "to_action_step" in saved else DEFAULT_TO_ACTION,
        "to_action_skip": list(saved["to_action_skip"]) if isinstance(saved.get("to_action_skip"), list) else [],
        "to_action_confirm": saved.get("to_action_confirm", True),
        "end_today_enabled": saved.get("end_today_enabled", True),
        "crisis_country": saved["crisis_country"] if "crisis_country" in saved else DEFAULT_CRISIS_COUNTRY,
        "weak_kindness": tuple(weak) if isinstance(weak, list) and len(weak) == 2 else DEFAULT_WEAK_KINDNESS,
        "keywords": {k: list(keywords[k]) if k in keywords else list(DEFAULT_KEYWORDS[k]) for k in KEYWORD_LISTS},
        "crisis_reply": {**DEFAULT_CRISIS_REPLY, **(saved.get("crisis_reply") or {})},
        **{k: saved[k] if k in saved else DEFAULT_ROLES[k] for k in ROLE_KEYS},
        "safety_steps": list(saved["safety_steps"]) if isinstance(saved.get("safety_steps"), list) else list(DEFAULT_SAFETY),
    }


async def load(db: AsyncSession) -> FlowConfig:
    saved = await _saved(db)
    rules = _rules_from(saved)
    # Every step in use is walked through in the admins' order, including
    # the ones that also answer on a trigger.
    return FlowConfig(
        order=await registry.active_flow_order(db),
        disabled=await registry.disabled_keys(db),
        limits=_limits_from(saved),
        # Set on the advanced settings page now (ai_params).
        history_turns=(await ai_params.load(db))["history_turns"],
        **rules,
    )


async def forget(db: AsyncSession, key: str) -> None:
    """After a step is deleted: drop every setting that pointed at it."""

    saved = await _saved(db)
    rules = _rules_from(saved)
    limits = saved.get("limits") if isinstance(saved.get("limits"), dict) else {}
    limits.pop(key, None)
    saved["limits"] = limits
    saved["to_action_step"] = None if rules["to_action_step"] == key else rules["to_action_step"]
    saved["to_action_skip"] = [k for k in rules["to_action_skip"] if k != key]
    for r in ROLE_KEYS:
        saved[r] = None if rules[r] == key else rules[r]
    saved["safety_steps"] = [k for k in rules["safety_steps"] if k != key]
    row = await db.get(AppSetting, SETTING_KEY) or AppSetting(key=SETTING_KEY, value="")
    row.value = json.dumps(saved, ensure_ascii=False)
    db.add(row)


async def for_admin(db: AsyncSession) -> dict[str, Any]:
    """Everything the admin page edits, with defaults filled in."""

    saved = await _saved(db)
    limits = _limits_from(saved)
    steps = [m.key for m in await registry.load_modules(db) if m.is_stage and m.key not in NO_LIMITS]
    return {
        "limits": {k: list(limits.get(k) or DEFAULT_LIMITS.get(k, (DEFAULT_MIN, DEFAULT_MAX))) for k in steps},
        # Lives in the AI-parameters settings now; the flow page only echoes it.
        "history_turns": (await ai_params.load(db))["history_turns"],
        **_rules_from(saved),
        "defaults": {
            "limits": {k: list(DEFAULT_LIMITS.get(k, (DEFAULT_MIN, DEFAULT_MAX))) for k in steps},
            "history_turns": DEFAULT_HISTORY,
            "weak_kindness": DEFAULT_WEAK_KINDNESS,
            "keywords": DEFAULT_KEYWORDS,
            "crisis_reply": DEFAULT_CRISIS_REPLY,
            "criticism": DEFAULT_CRITICISM,
            "to_action_step": DEFAULT_TO_ACTION,
            "to_action_skip": [],
            "to_action_confirm": True,
            "end_today_enabled": True,
            "crisis_country": DEFAULT_CRISIS_COUNTRY,
            **DEFAULT_ROLES,
            "safety_steps": DEFAULT_SAFETY,
        },
    }


def validate(payload: dict[str, Any], stage_keys: set[str]) -> str | None:
    """None if valid, else a short reason."""

    for key, (low, high) in payload["limits"].items():
        if key not in stage_keys or key in NO_LIMITS:
            return f"unknown step {key}"
        if not (1 <= low <= high <= MAX_TURNS_CAP):
            return f"bad limits for {key}"
    if not HISTORY_RANGE[0] <= payload["history_turns"] <= HISTORY_RANGE[1]:
        return "history_turns out of range"
    low, high = payload["weak_kindness"]
    if not 1 <= low <= high <= MAX_TURNS_CAP:
        return "bad weak_kindness limits"
    for name in KEYWORD_LISTS:
        words = payload["keywords"].get(name, [])
        if len(words) > MAX_KEYWORDS or any(not w or len(w) > MAX_KEYWORD_LENGTH for w in words):
            return f"bad keywords for {name}"
    if any(len(v) > MAX_CRISIS_REPLY for v in payload["crisis_reply"].values()):
        return "crisis_reply too long"
    c = payload["criticism"]
    if set(c) != set(DEFAULT_CRITICISM) or not all(0 <= v <= 100 for v in c.values()) or not 1 <= c["strong"]:
        return "bad criticism settings"
    if payload["to_action_step"] and payload["to_action_step"] not in stage_keys:
        return "unknown to_action step"
    if any(k not in stage_keys for k in payload["to_action_skip"]):
        return "unknown to_action_skip step"
    roles = [payload[k] for k in ROLE_KEYS if payload[k]]
    if any(k not in stage_keys for k in roles) or len(roles) != len(set(roles)):
        return "bad step roles"
    if any(k not in stage_keys for k in payload["safety_steps"]):
        return "unknown safety step"
    if len(payload["crisis_country"]) > 8:
        return "bad crisis_country"
    return None


async def save(db: AsyncSession, payload: dict[str, Any], admin_id: str | None) -> None:
    row = await db.get(AppSetting, SETTING_KEY)
    if row is None:
        row = AppSetting(key=SETTING_KEY, value="")
    row.value = json.dumps(
        {
            "limits": {k: list(v) for k, v in payload["limits"].items()},
            "history_turns": payload["history_turns"],
            "weak_kindness": list(payload["weak_kindness"]),
            "keywords": {k: payload["keywords"].get(k, []) for k in KEYWORD_LISTS},
            "crisis_reply": payload["crisis_reply"],
            "criticism": payload["criticism"],
            "to_action_step": payload["to_action_step"],
            "to_action_skip": list(dict.fromkeys(payload["to_action_skip"])),
            "to_action_confirm": payload["to_action_confirm"],
            "end_today_enabled": payload["end_today_enabled"],
            "crisis_country": payload["crisis_country"],
            **{k: payload[k] for k in ROLE_KEYS},
            "safety_steps": list(dict.fromkeys(payload["safety_steps"])),
        },
        ensure_ascii=False,
    )
    row.updated_by_id = admin_id
    db.add(row)
