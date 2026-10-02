from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DialogueIntent, Language
from app.prompts import registry
from app.prompts.base import build_system_prompt
from app.prompts.principles import titled_sections

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
    preview only) substitutes unsaved draft text, reported as version -1.

    Disabled blocks are left out. Which flow is used is still decided here in
    code; admin-added flow blocks only ride along with the flow they belong
    to."""

    flow_key = flow_key_for(intent, self_criticism_level)
    modules = [
        m
        for m in await registry.load_modules(db)
        if m.enabled and (m.group != "flow" or m.key == flow_key or m.flow_key == flow_key)
    ]
    keys = [m.key for m in modules]
    resolved = await registry.resolve(db, keys, language)
    for key, content in (overrides or {}).items():
        if key in resolved:
            resolved[key] = registry.ResolvedPrompt(content, -1)

    def text(group: str) -> str:
        return titled_sections([(m.title(language), resolved[m.key].content) for m in modules if m.group == group])

    flow_blocks = [m for m in modules if m.group == "flow"]
    # The built-in flow's own text goes first and untitled (it opens with its
    # own "当前阶段：…" line); blocks admins added to it follow under their names.
    flow_text = "\n\n".join(
        part
        for part in (
            resolved[flow_key].content.strip() if any(m.key == flow_key for m in flow_blocks) else "",
            titled_sections([(m.title(language), resolved[m.key].content) for m in flow_blocks if m.key != flow_key]),
        )
        if part
    )

    prompt = build_system_prompt(
        text("rules"),
        flow_text,
        language,
        registry.FLOW_FORMAT_RULES[flow_key][language],
        text("other"),
    )
    used = {key: resolved[key].version for key in keys if resolved[key].content.strip()}
    return prompt, used
