"""Crisis screening: plain keyword matching, run on every user message. A hit
adds the crisis prompt (app/services/agent_config.py) to that reply."""

import re

from app.services.agent_config import CRISIS_KEYWORDS


def _pattern(word: str) -> str:
    # Plain words, not regex; a space matches any spacing.
    return r"\s*".join(re.escape(part) for part in word.split())


def is_crisis(text: str) -> bool:
    return any(re.search(_pattern(w), text, flags=re.IGNORECASE) for w in CRISIS_KEYWORDS if w.strip())
