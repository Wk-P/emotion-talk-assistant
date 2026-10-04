from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Language
from app.prompts import registry
from app.prompts.base import build_system_prompt
from app.prompts.principles import titled_sections


def _stage_heading(stage: registry.Module, language: Language, sys: dict[str, str]) -> str:
    # Names the current step, so a step an admin added (with only their own
    # text) reads as clearly as a built-in one.
    heading = sys["system.stage_heading"].replace("{name}", stage.title(language))
    return f"{heading}\n" if heading else ""


async def build_prompt(
    db: AsyncSession,
    flow_key: str,
    language: Language,
    overrides: dict[str, str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Returns the system prompt plus {key: version} of the blocks it was
    built from, for recording on the resulting message. `overrides` (admin
    preview only) substitutes unsaved draft text, reported as version -1.

    Disabled blocks are left out. `flow_key` is the stage, decided in code
    (app/services/flow.py); admin-added flow blocks only ride along with the
    stage they belong to."""

    modules = [
        m
        for m in await registry.load_modules(db)
        if m.enabled and m.group != "system" and (m.group != "flow" or m.key == flow_key or m.flow_key == flow_key)
    ]
    sys = await registry.system_texts(db, language)
    keys = [m.key for m in modules]
    resolved = await registry.resolve(db, keys, language)
    for key, content in (overrides or {}).items():
        if key in resolved:
            resolved[key] = registry.ResolvedPrompt(content, -1)

    def text(group: str) -> str:
        return titled_sections([(m.title(language), resolved[m.key].content) for m in modules if m.group == group])

    flow_blocks = [m for m in modules if m.group == "flow"]
    stage = next((m for m in flow_blocks if m.key == flow_key), None)
    # The built-in flow's own text goes first and untitled (it opens with its
    # own "当前阶段：…" line); blocks admins added to it follow under their names.
    flow_text = "\n\n".join(
        part
        for part in (
            _stage_heading(stage, language, sys) + resolved[flow_key].content.strip() if stage else "",
            titled_sections([(m.title(language), resolved[m.key].content) for m in flow_blocks if m.key != flow_key]),
        )
        if part
    )

    prompt = build_system_prompt(text("rules"), flow_text, flow_key, sys, text("other"))
    used = {key: resolved[key].version for key in keys if resolved[key].content.strip()}
    return prompt, used
