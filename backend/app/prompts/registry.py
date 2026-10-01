"""The prompt blocks admins can edit from the admin UI, and how the text in
effect for each is resolved (see app/models/prompt.py).

Only tone/behavior text is editable. Deliberately NOT in here, and so never
editable from the UI:
  - the JSON output-format suffix (app/services/llm.py) — the frontend
    parses the reply, so a bad edit would break every turn
  - candidate field/type names (FORMAT_RULES in base.py and each flow
    module) — same reason, and they read as jargon to non-technical admins
  - risk screening, crisis copy and the disclaimer (app/services/safety.py,
    app/services/dialogue_state.py) — safety-critical, enforced in code
  - flow routing (app/prompts/router.py)
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Language
from app.models.prompt import PromptVersion
from app.prompts import base, emotion_exploration, intent_question, recovery_plan, self_kindness, stabilization

ROLE_RULES = "role_rules"
FLOW_EMOTION_EXPLORATION = "flow.emotion_exploration"
FLOW_STABILIZATION = "flow.stabilization"
FLOW_RECOVERY_PLAN = "flow.recovery_plan"
FLOW_SELF_KINDNESS = "flow.self_kindness"
ASSISTANT_INTENT_QUESTION = "assistant.intent_question"

# Ordered as the admin UI lists them.
DEFAULTS: dict[str, dict[Language, str]] = {
    ROLE_RULES: base.ROLE_RULES,
    FLOW_EMOTION_EXPLORATION: emotion_exploration.FLOW_INSTRUCTIONS,
    FLOW_STABILIZATION: stabilization.FLOW_INSTRUCTIONS,
    FLOW_RECOVERY_PLAN: recovery_plan.FLOW_INSTRUCTIONS,
    FLOW_SELF_KINDNESS: self_kindness.FLOW_INSTRUCTIONS,
    ASSISTANT_INTENT_QUESTION: intent_question.TEXT,
}

# Fixed, code-only rules appended after each flow's (editable) text — see
# base.build_system_prompt. Not exposed to the admin UI.
FLOW_FORMAT_RULES: dict[str, dict[Language, str]] = {
    FLOW_EMOTION_EXPLORATION: emotion_exploration.FORMAT_RULES,
    FLOW_STABILIZATION: stabilization.FORMAT_RULES,
    FLOW_RECOVERY_PLAN: recovery_plan.FORMAT_RULES,
    FLOW_SELF_KINDNESS: self_kindness.FORMAT_RULES,
}

MAX_CONTENT_LENGTH = 20000


class ResolvedPrompt:
    def __init__(self, content: str, version: int):
        self.content = content
        self.version = version  # 0 = code default


async def latest_versions(db: AsyncSession, keys: list[str], language: Language) -> dict[str, PromptVersion]:
    latest = (
        select(PromptVersion.key, func.max(PromptVersion.version).label("version"))
        .where(PromptVersion.language == language, PromptVersion.key.in_(keys))
        .group_by(PromptVersion.key)
        .subquery()
    )
    result = await db.execute(
        select(PromptVersion).join(
            latest,
            (PromptVersion.key == latest.c.key) & (PromptVersion.version == latest.c.version),
        ).where(PromptVersion.language == language)
    )
    return {row.key: row for row in result.scalars().all()}


async def resolve(db: AsyncSession, keys: list[str], language: Language) -> dict[str, ResolvedPrompt]:
    rows = await latest_versions(db, keys, language)
    return {
        key: ResolvedPrompt(rows[key].content, rows[key].version)
        if key in rows
        else ResolvedPrompt(DEFAULTS[key][language], 0)
        for key in keys
    }
