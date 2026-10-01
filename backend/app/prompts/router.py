from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DialogueIntent, Language
from app.prompts import registry
from app.prompts.base import build_system_prompt

_FLOW_MAP = {
    DialogueIntent.VENT: registry.FLOW_EMOTION_EXPLORATION,
    DialogueIntent.ORGANIZE: registry.FLOW_EMOTION_EXPLORATION,
    DialogueIntent.STABILIZE: registry.FLOW_STABILIZATION,
    DialogueIntent.METHOD: registry.FLOW_RECOVERY_PLAN,
}

# Information requests are answered directly by the safety/resource endpoint,
# not by the general LLM flow (design principle 8.4: resource info comes from
# a verified table, never AI-generated) — no prompt module needed here.


def flow_key_for(intent: DialogueIntent, self_criticism_level: float) -> str:
    # Design principle 4 / 9.3: strong self-criticism preempts the routed flow
    # in favor of acceptance support.
    if self_criticism_level >= 0.5 and intent != DialogueIntent.STABILIZE:
        return registry.FLOW_SELF_KINDNESS
    return _FLOW_MAP.get(intent, registry.FLOW_EMOTION_EXPLORATION)


async def build_prompt(
    db: AsyncSession,
    intent: DialogueIntent,
    language: Language,
    self_criticism_level: float,
    overrides: dict[str, str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Returns the system prompt plus {key: version} of the blocks it was
    built from, for recording on the resulting message. `overrides` (admin
    preview only) substitutes unsaved draft text, reported as version -1."""

    flow_key = flow_key_for(intent, self_criticism_level)
    keys = [registry.ROLE_RULES, flow_key]
    resolved = await registry.resolve(db, keys, language)
    for key, content in (overrides or {}).items():
        if key in resolved:
            resolved[key] = registry.ResolvedPrompt(content, -1)

    prompt = build_system_prompt(
        resolved[registry.ROLE_RULES].content,
        resolved[flow_key].content,
        language,
        registry.FLOW_FORMAT_RULES[flow_key][language],
    )
    return prompt, {key: resolved[key].version for key in keys}
