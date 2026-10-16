"""The flow settings admins control from the admin page ("对话流程顺序"), beyond
the step order and wording:

  - per step, the minimum user turns before the model's "this step is done"
    is accepted, and the maximum after which the step moves on regardless;
  - the purpose buttons shown in the purpose step: their wording (zh/ko)
    and which later step each one jumps to (or none: the next step);
  - how many recent messages the model sees each turn;
  - the rules that used to be fixed in code: how many things the user must
    have said before the summary card may show, the shorter turn limits of
    self_kindness when self-criticism is weak, the crisis / "overwhelmed" /
    self-criticism word lists, how self-criticism is scored, which step each
    checkpoint card belongs to, where "tell me what to do" / "that's enough
    for today" lead, and the crisis reply text and resources shown.

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

DEFAULT_SUMMARY_MIN_TURNS = 3
SUMMARY_MIN_RANGE = (1, 20)
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
# The two checkpoint cards and the step each may show in (None = never).
CARD_TYPES = ("seb_summary", "plan_form")
DEFAULT_CARD_STEPS: dict[str, str | None] = {"seb_summary": stages.LISTEN, "plan_form": stages.ACT}
# "Tell me what to do": the step it jumps to (None = ignored).
DEFAULT_TO_ACTION = stages.ACT
# Crisis resources shown: this country's ("" = all).
DEFAULT_CRISIS_COUNTRY = "KR"


@dataclass
class FlowConfig:
    # Active steps in order, ending with closing (registry.active_flow_order).
    order: list[str]
    limits: dict[str, tuple[int, int]] = field(default_factory=dict)
    purposes: list[dict[str, Any]] = field(default_factory=lambda: [dict(p) for p in DEFAULT_PURPOSES])
    history_turns: int = DEFAULT_HISTORY
    summary_min_turns: int = DEFAULT_SUMMARY_MIN_TURNS
    weak_kindness: tuple[int, int] = DEFAULT_WEAK_KINDNESS
    keywords: dict[str, list[str]] = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_KEYWORDS.items()})
    crisis_reply: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_CRISIS_REPLY))
    criticism: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CRITICISM))
    card_steps: dict[str, str | None] = field(default_factory=lambda: dict(DEFAULT_CARD_STEPS))
    to_action_step: str | None = DEFAULT_TO_ACTION
    end_today_enabled: bool = True
    # The step the purpose buttons are attached to (None = removed).
    button_step: str | None = stages.PURPOSE
    crisis_country: str = DEFAULT_CRISIS_COUNTRY

    def card_for(self, stage: str) -> str | None:
        return next((c for c, k in self.card_steps.items() if k == stage), None)

    def crisis_text(self, language: Language) -> str:
        return (self.crisis_reply.get(language.value) or "").strip() or DEFAULT_CRISIS_REPLY[language.value]

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


def _rules_from(saved: dict[str, Any]) -> dict[str, Any]:
    """The code-rule settings, defaults filled in. A keyword list saved empty
    stays empty (admins may turn a list off); one never saved is the default."""

    weak = saved.get("weak_kindness")
    keywords = dict(saved["keywords"]) if isinstance(saved.get("keywords"), dict) else {}
    if "crisis" not in keywords and keywords.get("crisis_extra"):
        # Saved when the built-in crisis words were fixed and only extras were set.
        keywords["crisis"] = [*DEFAULT_KEYWORDS["crisis"], *keywords["crisis_extra"]]
    card_steps = saved.get("card_steps") if isinstance(saved.get("card_steps"), dict) else {}
    return {
        "criticism": {**DEFAULT_CRITICISM, **(saved.get("criticism") or {})},
        "card_steps": {c: card_steps[c] if c in card_steps else DEFAULT_CARD_STEPS[c] for c in CARD_TYPES},
        "to_action_step": saved["to_action_step"] if "to_action_step" in saved else DEFAULT_TO_ACTION,
        "end_today_enabled": saved.get("end_today_enabled", True),
        "button_step": saved["button_step"] if "button_step" in saved else stages.PURPOSE,
        "crisis_country": saved["crisis_country"] if "crisis_country" in saved else DEFAULT_CRISIS_COUNTRY,
        "summary_min_turns": saved.get("summary_min_turns") or DEFAULT_SUMMARY_MIN_TURNS,
        "weak_kindness": tuple(weak) if isinstance(weak, list) and len(weak) == 2 else DEFAULT_WEAK_KINDNESS,
        "keywords": {k: list(keywords[k]) if k in keywords else list(DEFAULT_KEYWORDS[k]) for k in KEYWORD_LISTS},
        "crisis_reply": {**DEFAULT_CRISIS_REPLY, **(saved.get("crisis_reply") or {})},
    }


async def load(db: AsyncSession) -> FlowConfig:
    saved = await _saved(db)
    return FlowConfig(
        order=await registry.active_flow_order(db),
        limits=_limits_from(saved),
        purposes=saved.get("purposes") or [dict(p) for p in DEFAULT_PURPOSES],
        history_turns=saved.get("history_turns") or DEFAULT_HISTORY,
        **_rules_from(saved),
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
        **_rules_from(saved),
        "defaults": {
            "limits": {k: list(DEFAULT_LIMITS.get(k, (DEFAULT_MIN, DEFAULT_MAX))) for k in steps},
            "purposes": DEFAULT_PURPOSES,
            "history_turns": DEFAULT_HISTORY,
            "summary_min_turns": DEFAULT_SUMMARY_MIN_TURNS,
            "weak_kindness": DEFAULT_WEAK_KINDNESS,
            "keywords": DEFAULT_KEYWORDS,
            "crisis_reply": DEFAULT_CRISIS_REPLY,
            "criticism": DEFAULT_CRITICISM,
            "card_steps": DEFAULT_CARD_STEPS,
            "to_action_step": DEFAULT_TO_ACTION,
            "end_today_enabled": True,
            "button_step": stages.PURPOSE,
            "crisis_country": DEFAULT_CRISIS_COUNTRY,
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
    if not SUMMARY_MIN_RANGE[0] <= payload["summary_min_turns"] <= SUMMARY_MIN_RANGE[1]:
        return "summary_min_turns out of range"
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
    if set(payload["card_steps"]) != set(CARD_TYPES):
        return "bad card_steps"
    steps = [k for k in payload["card_steps"].values() if k]
    if len(steps) != len(set(steps)) or any(k not in stage_keys or k in NO_LIMITS for k in steps):
        return "bad card_steps"
    b = payload["button_step"]
    if b and (b not in stage_keys or b in (stages.CLOSING, stages.STABILIZATION, stages.ENDING) or b in steps):
        return "bad button_step"
    if payload["to_action_step"] and payload["to_action_step"] not in stage_keys:
        return "unknown to_action step"
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
            "purposes": payload["purposes"],
            "history_turns": payload["history_turns"],
            "summary_min_turns": payload["summary_min_turns"],
            "weak_kindness": list(payload["weak_kindness"]),
            "keywords": {k: payload["keywords"].get(k, []) for k in KEYWORD_LISTS},
            "crisis_reply": payload["crisis_reply"],
            "criticism": payload["criticism"],
            "card_steps": payload["card_steps"],
            "to_action_step": payload["to_action_step"],
            "end_today_enabled": payload["end_today_enabled"],
            "button_step": payload["button_step"],
            "crisis_country": payload["crisis_country"],
        },
        ensure_ascii=False,
    )
    row.updated_by_id = admin_id
    db.add(row)
