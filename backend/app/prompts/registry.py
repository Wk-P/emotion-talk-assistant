"""The prompt blocks admins can edit from the admin UI, and how the text in
effect for each is resolved (see app/models/prompt.py).

Only tone/behavior text is editable. Deliberately NOT in here, and so never
editable from the UI:
  - the JSON output-format suffix (app/services/llm.py) — the frontend
    parses the reply, so a bad edit would break every turn
  - candidate field/type names and progress signals (FORMAT_RULES in
    base.py and stages.py) — same reason, and they read as jargon to non-technical admins
  - risk screening, crisis copy and the disclaimer (app/services/safety.py,
    app/services/dialogue_state.py) — safety-critical, enforced in code
  - which stage is current (app/services/flow.py)

Admins can also rename or disable any block and add their own (see
app/models/prompt.PromptModule); load_modules() gives the full, ordered set.
"""

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.models.enums import Language
from app.models.prompt import PromptModule, PromptVersion
from app.prompts import principles, stages

# The common principles, one key per section (e.g. "rules.listening").
RULE_KEYS = principles.KEYS
# The conversation stages (app/prompts/stages.py), in flowchart order; which
# one is used each turn is decided in app/services/flow.py.
FLOW_KEYS = stages.KEYS

# Default names, as the admin UI shows them; also used as the 【title】 of an
# admin-added block in the prompt when it has no name in that language.
DEFAULT_TITLES: dict[str, dict[Language, str]] = {**principles.TITLES, **stages.TITLES}

GROUPS = ("rules", "flow", "other")
CUSTOM_PREFIX = "custom."
MAX_MODULE_NAME_LENGTH = 40

# Ordered as the admin UI lists them.
DEFAULTS: dict[str, dict[Language, str]] = {**principles.DEFAULTS, **stages.FLOW_INSTRUCTIONS}

# Fixed, code-only rules appended after each stage's (editable) text — see
# base.build_system_prompt. Not exposed to the admin UI.
FLOW_FORMAT_RULES: dict[str, dict[Language, str]] = stages.FORMAT_RULES

MAX_CONTENT_LENGTH = 20000


@dataclass
class Module:
    key: str
    group: str
    built_in: bool
    enabled: bool
    # Names an admin set, by language value ("zh"/"ko"); empty = default.
    names: dict[str, str]
    flow_key: str | None = None  # admin-added flow blocks: the stage they belong to
    # A conversation stage (built-in, or added by an admin as a step of its
    # own) rather than a block attached to one.
    is_stage: bool = False

    def title(self, language: Language) -> str:
        name = (self.names.get(language.value) or "").strip()
        if name:
            return name
        if self.key in DEFAULT_TITLES:
            return DEFAULT_TITLES[self.key][language]
        # Admin-added block named only in the other language.
        return next((n for n in self.names.values() if n.strip()), "")


# The stage order admins set on the admin page (a JSON list of stage keys,
# without closing — always last — and stabilization / ending — not in the
# sequence).
FLOW_ORDER_SETTING = "flow_order"
_FIXED_STAGES = (stages.CLOSING, stages.STABILIZATION, stages.ENDING)
DEFAULT_SEQUENCE = [k for k in stages.ORDER if k != stages.CLOSING]


async def _saved_order(db: AsyncSession) -> list[str]:
    row = await db.get(AppSetting, FLOW_ORDER_SETTING)
    try:
        value = json.loads(row.value) if row and row.value else []
    except ValueError:
        return []
    return [k for k in value if isinstance(k, str)] if isinstance(value, list) else []


async def load_modules(db: AsyncSession) -> list[Module]:
    """Every block in the order it is listed and sent: built-in principles,
    then added principles; the stages in the admins' order (each followed by
    the blocks added to it), then closing and stabilization; then the
    "other" blocks. Added blocks keep their creation order."""

    rows = (await db.execute(select(PromptModule).order_by(PromptModule.created_at, PromptModule.key))).scalars().all()
    by_key = {r.key: r for r in rows}
    custom = [r for r in rows if r.key.startswith(CUSTOM_PREFIX)]

    def built_in(key: str, group: str) -> Module:
        row = by_key.get(key)
        return Module(
            key, group, True, row.enabled if row else True, dict(row.names or {}) if row else {}, None, group == "flow"
        )

    def added(row: PromptModule) -> Module:
        stage = row.group == "flow" and not row.flow_key
        return Module(row.key, row.group, False, row.enabled, dict(row.names or {}), row.flow_key, stage)

    movable = DEFAULT_SEQUENCE + [r.key for r in custom if r.group == "flow" and not r.flow_key]
    saved = await _saved_order(db)
    sequence = [k for k in saved if k in movable] + [k for k in movable if k not in saved]

    out = [built_in(k, "rules") for k in RULE_KEYS]
    out += [added(r) for r in custom if r.group == "rules"]
    for stage_key in [*sequence, *_FIXED_STAGES]:
        out.append(built_in(stage_key, "flow") if stage_key in FLOW_KEYS else added(by_key[stage_key]))
        out += [added(r) for r in custom if r.group == "flow" and r.flow_key == stage_key]
    out += [added(r) for r in custom if r.group == "other"]
    return out


def flow_sequence(modules: list[Module]) -> list[str]:
    """The stages admins can order, in their order (turned-off ones too)."""

    return [m.key for m in modules if m.is_stage and m.key not in _FIXED_STAGES]


async def active_flow_order(db: AsyncSession) -> list[str]:
    """What conversations go through: the admins' order without turned-off
    stages, then closing (always last, even if its text is turned off)."""

    modules = await load_modules(db)
    enabled = {m.key for m in modules if m.enabled}
    return [k for k in flow_sequence(modules) if k in enabled] + [stages.CLOSING]


async def save_flow_order(db: AsyncSession, order: list[str], admin_id: str | None) -> None:
    row = await db.get(AppSetting, FLOW_ORDER_SETTING)
    if row is None:
        row = AppSetting(key=FLOW_ORDER_SETTING, value="")
    row.value = json.dumps(order)
    row.updated_by_id = admin_id
    db.add(row)


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
