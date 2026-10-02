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

Admins can also rename or disable any block and add their own (see
app/models/prompt.PromptModule); load_modules() gives the full, ordered set.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Language
from app.models.prompt import PromptModule, PromptVersion
from app.prompts import (
    principles,
    emotion_exploration,
    recovery_plan,
    self_kindness,
    stabilization,
)

# The common principles, one key per section (e.g. "rules.listening").
RULE_KEYS = principles.KEYS
FLOW_EMOTION_EXPLORATION = "flow.emotion_exploration"
FLOW_STABILIZATION = "flow.stabilization"
FLOW_RECOVERY_PLAN = "flow.recovery_plan"
FLOW_SELF_KINDNESS = "flow.self_kindness"
FLOW_KEYS = [FLOW_EMOTION_EXPLORATION, FLOW_STABILIZATION, FLOW_RECOVERY_PLAN, FLOW_SELF_KINDNESS]

# Default names, as the admin UI shows them; also used as the 【title】 of an
# admin-added block in the prompt when it has no name in that language.
FLOW_TITLES: dict[str, dict[Language, str]] = {
    FLOW_EMOTION_EXPLORATION: {Language.ZH: "陪用户聊感受时", Language.KO: "감정을 함께 이야기할 때"},
    FLOW_STABILIZATION: {Language.ZH: "帮用户平静下来时", Language.KO: "마음을 가라앉히도록 도울 때"},
    FLOW_RECOVERY_PLAN: {Language.ZH: "和用户一起想办法时", Language.KO: "함께 방법을 찾을 때"},
    FLOW_SELF_KINDNESS: {Language.ZH: "用户责怪自己时", Language.KO: "사용자가 자신을 탓할 때"},
}
DEFAULT_TITLES: dict[str, dict[Language, str]] = {**principles.TITLES, **FLOW_TITLES}

GROUPS = ("rules", "flow", "other")
CUSTOM_PREFIX = "custom."
MAX_MODULE_NAME_LENGTH = 40

# Ordered as the admin UI lists them.
DEFAULTS: dict[str, dict[Language, str]] = {
    **principles.DEFAULTS,
    FLOW_EMOTION_EXPLORATION: emotion_exploration.FLOW_INSTRUCTIONS,
    FLOW_STABILIZATION: stabilization.FLOW_INSTRUCTIONS,
    FLOW_RECOVERY_PLAN: recovery_plan.FLOW_INSTRUCTIONS,
    FLOW_SELF_KINDNESS: self_kindness.FLOW_INSTRUCTIONS,
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


@dataclass
class Module:
    key: str
    group: str
    built_in: bool
    enabled: bool
    # Names an admin set, by language value ("zh"/"ko"); empty = default.
    names: dict[str, str]
    flow_key: str | None = None  # admin-added flow blocks: the flow they belong to

    def title(self, language: Language) -> str:
        name = (self.names.get(language.value) or "").strip()
        if name:
            return name
        if self.key in DEFAULT_TITLES:
            return DEFAULT_TITLES[self.key][language]
        # Admin-added block named only in the other language.
        return next((n for n in self.names.values() if n.strip()), "")


async def load_modules(db: AsyncSession) -> list[Module]:
    """Every block in the order it is listed and sent: built-in principles,
    then added principles; each built-in flow followed by the blocks added to
    it; then the "other" blocks. Added blocks keep their creation order."""

    rows = (await db.execute(select(PromptModule).order_by(PromptModule.created_at, PromptModule.key))).scalars().all()
    by_key = {r.key: r for r in rows}
    custom = [r for r in rows if r.key.startswith(CUSTOM_PREFIX)]

    def built_in(key: str, group: str) -> Module:
        row = by_key.get(key)
        return Module(key, group, True, row.enabled if row else True, dict(row.names or {}) if row else {})

    def added(row: PromptModule) -> Module:
        return Module(row.key, row.group, False, row.enabled, dict(row.names or {}), row.flow_key)

    out = [built_in(k, "rules") for k in RULE_KEYS]
    out += [added(r) for r in custom if r.group == "rules"]
    for flow_key in FLOW_KEYS:
        out.append(built_in(flow_key, "flow"))
        out += [added(r) for r in custom if r.group == "flow" and r.flow_key == flow_key]
    out += [added(r) for r in custom if r.group == "other"]
    return out


def default_content(key: str, language: Language) -> str:
    # Admin-added blocks start out empty.
    return DEFAULTS[key][language] if key in DEFAULTS else ""


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
        else ResolvedPrompt(default_content(key, language), 0)
        for key in keys
    }
