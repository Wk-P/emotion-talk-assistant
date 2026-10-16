"""Deterministic safety/risk screening (design principle 8.4).

Runs as plain code before AND after every model call — it must never depend
solely on the LLM's own judgment for a decision this consequential. This is a
keyword-based starting point; before any real user contact, have it reviewed
and extended by a qualified clinician/safety reviewer for both languages.
"""

import re

from app.models.enums import RiskLevel

# All word lists are the admins' (admin page "程序规则", defaults in
# app/services/flow_config.py); the screening itself stays here in code.


def _matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _word_patterns(words: list[str]) -> list[str]:
    # Admin words are plain text, not regex; a space matches any spacing.
    return [r"\s*".join(re.escape(part) for part in w.split()) for w in words if w.strip()]


def screen_text(text: str, keywords: dict[str, list[str]]) -> RiskLevel:
    if _matches(text, _word_patterns(keywords.get("crisis", []))):
        return RiskLevel.CRISIS
    if _matches(text, _word_patterns(keywords.get("watch", []))):
        return RiskLevel.WATCH
    return RiskLevel.NONE


# --- Self-criticism signal (design principle 4, 9.3) --------------------------------


def bump_self_criticism(
    text: str, current_level: float, keywords: dict[str, list[str]], criticism: dict[str, int]
) -> float:
    """Nudges the rolling self-criticism level; used to prioritize acceptance
    support over exploration/action-planning flows (never a diagnostic score)."""
    hit = _matches(text, _word_patterns(keywords.get("self_criticism", [])))
    if hit:
        return min(1.0, current_level + criticism["up"] / 100)
    return max(0.0, current_level - criticism["down"] / 100)
