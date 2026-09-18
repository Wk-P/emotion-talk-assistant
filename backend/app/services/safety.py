"""Deterministic safety/risk screening (design principle 8.4).

Runs as plain code before AND after every model call — it must never depend
solely on the LLM's own judgment for a decision this consequential. This is a
keyword-based starting point; before any real user contact, have it reviewed
and extended by a qualified clinician/safety reviewer for both languages.
"""

import re

from app.models.enums import RiskLevel

# Explicit self-harm / harm-to-others / acute-crisis language.
_CRISIS_PATTERNS_ZH = [
    r"不想活", r"自杀", r"想死", r"结束生命", r"伤害自己", r"割腕", r"想杀", r"杀了他", r"杀了她",
]
_CRISIS_PATTERNS_KO = [
    r"죽고\s*싶", r"자살", r"자해", r"삶을\s*끝", r"죽이고\s*싶", r"살고\s*싶지\s*않",
]

# Elevated distress language that warrants a closer check-in, but is not itself
# a crisis signal (avoid over-triggering on ordinary venting).
_WATCH_PATTERNS_ZH = [r"撑不下去", r"崩溃", r"绝望", r"没有意义了"]
_WATCH_PATTERNS_KO = [r"버틸\s*수\s*없", r"무너질\s*것\s*같", r"희망이\s*없", r"의미가\s*없"]


def _matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def screen_text(text: str) -> RiskLevel:
    if _matches(text, _CRISIS_PATTERNS_ZH) or _matches(text, _CRISIS_PATTERNS_KO):
        return RiskLevel.CRISIS
    if _matches(text, _WATCH_PATTERNS_ZH) or _matches(text, _WATCH_PATTERNS_KO):
        return RiskLevel.WATCH
    return RiskLevel.NONE


# --- Self-criticism signal (design principle 4, 9.3) --------------------------------

_SELF_CRITICISM_PATTERNS_ZH = [r"我很没用", r"我真差", r"都怪我", r"我不够好", r"我很失败", r"我什么都做不好"]
_SELF_CRITICISM_PATTERNS_KO = [r"나는\s*쓸모없", r"내\s*잘못", r"나는\s*부족", r"나는\s*실패자", r"나\s*때문"]


def bump_self_criticism(text: str, current_level: float) -> float:
    """Nudges the rolling self-criticism level; used to prioritize acceptance
    support over exploration/action-planning flows (never a diagnostic score)."""
    hit = _matches(text, _SELF_CRITICISM_PATTERNS_ZH) or _matches(text, _SELF_CRITICISM_PATTERNS_KO)
    if hit:
        return min(1.0, current_level + 0.25)
    return max(0.0, current_level - 0.05)
