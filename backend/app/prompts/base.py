"""Shared system-prompt scaffolding.

Two parts, by design: the code-fixed technical rules (output format, card and
signal fields, reply language) come first; everything about how to talk —
the common principles, the stage's instructions and admins' own blocks, all
editable in the admin UI — comes last and takes priority over anything
before it except those technical rules. The project's behaviour is meant to
be shaped by the admins' prompt, not by code; code only decides which stage
is current (app/services/flow.py) and keeps the safety and data rules.
Nothing here should be the sole enforcement of a safety-critical rule (risk
screening and consent gating happen in app/services/safety.py and the API
layer, in code) — this is tone/behavior guidance for the model, not a guard.
Which candidate cards may reach the user at all is enforced in code too
(app/services/dialogue_state.py), not just asked for here.
"""

from app.models.enums import Language
from app.prompts import stages


def _flow_format(flow_key: str, sys: dict[str, str]) -> str:
    if flow_key == stages.LISTEN:
        return sys["system.card_listen"]
    if flow_key == stages.ACT:
        return sys["system.card_act"]
    return sys["system.no_cards"]


def _signals(flow_key: str, sys: dict[str, str]) -> str:
    if flow_key in (stages.STABILIZATION, stages.ENDING):
        return ""
    extra = sys["system.self_check_signal"] if flow_key == stages.SELF_CHECK else ""
    return "\n".join(p for p in (sys["system.signals"], extra) if p)


def build_system_prompt(
    rules_text: str,
    flow_instructions: str,
    flow_key: str,
    sys: dict[str, str],
    other_text: str = "",
) -> str:
    # The program's own part (sys, app/prompts/system.py) first, then the
    # admins' blocks under the priority header, then the output format. All
    # of it is admin-editable; a turned-off piece is simply left out.
    technical = "\n".join(
        p for p in (sys["system.format"], _flow_format(flow_key, sys), _signals(flow_key, sys), sys["system.reply_language"]) if p
    )
    sections = [s for s in (rules_text, flow_instructions, other_text) if s.strip()]
    admin = "\n\n".join(p for p in (sys["system.priority_header"], "\n\n---\n".join(sections)) if p)
    prompt = "\n\n---\n".join(p for p in (technical, admin, sys["system.output_json"]) if p)
    # OpenAI's JSON mode refuses a request whose messages never say "JSON".
    if "json" not in prompt.lower():
        prompt += "\n\nJSON"
    return prompt
