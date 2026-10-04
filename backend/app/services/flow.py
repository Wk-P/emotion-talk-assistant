"""Which conversation stage a session is in, and when it moves on — decided
here in code. The ORDER of the stages is the admins' (admin page "对话流程顺序",
app/prompts/registry.flow_order); the default follows
documents/01_研究资料/애플리케이션 플로우차트.png and the project lead's STEP 1-5
(documents/02_内容与需求/对话运行Prompt_负责人.md):

  listen → purpose → explore → self_check → self_kindness → regulate → act → closing

Some built-in stages carry behaviour of their own, wherever they are placed:
  - listen ends when the user confirms the summary, on the card or in their
    own words (the model's stage_done, once the summary has been shown);
  - purpose ends on the user's answer (purpose buttons or typed); "先让自己平静"
    jumps ahead to regulate, "一起想想接下来怎么办" to act, if those come later;
  - self_check ends on the user's answer and sets a branch: strong → full
    self_kindness; weak / none → self_kindness kept brief. Regulate follows
    either way (the lead's STEP 4 A/B);
  - act ends when the user confirms the plan card;
  - closing is always last.
Every other stage (including stages admins add) ends when the model reports
its goal reached (stage_done) after a minimum number of user turns, or at a
maximum — both admin-set per step (app/services/flow_config.py). The toolbar "跳过" skips the current stage; "告诉我怎么办" / "今天先到这里"
(reported by the model as user_request) jump to act / closing.

A turn screened as overwhelmed (RiskLevel.WATCH) is answered with the
stabilization prompt without changing the stage.
"""

from typing import Any

from app.models.enums import Language
from app.models.session import ConversationSession
from app.prompts import stages
from app.services.flow_config import FlowConfig

# Stages that end on something the user does, not on the model's stage_done.
_USER_ENDED = {stages.LISTEN, stages.PURPOSE, stages.SELF_CHECK, stages.CLOSING}
# Weak or no self-criticism: brief acceptance only ("自我批评不强时，不要反复进行自我友善活动").
_WEAK_SELF_KINDNESS_MIN, _WEAK_SELF_KINDNESS_MAX = 1, 2

PURPOSE_CARD = "purpose_options"


def state(session: ConversationSession, cfg: FlowConfig) -> dict[str, Any]:
    order = cfg.order

    s = dict(session.flow_state or {})
    stage = s.get("stage")
    if not stage:
        # New conversation, or one from before stages existed: past the
        # summary means past listening.
        seb = (session.confirmed_context or {}).get("seb_entries")
        s = {"stage": order[0], "turns": 0}
        if seb and order[0] == stages.LISTEN:
            _advance(s, cfg)
    elif stage not in order:
        # The admins turned this stage off or removed it mid-conversation.
        if stage in stages.ORDER:
            _advance(s, cfg)
        else:
            _enter(s, next((k for k in order if k not in (stages.LISTEN, stages.PURPOSE)), order[-1]))
    return s


def _enter(s: dict[str, Any], stage: str) -> None:
    s["stage"] = stage
    s["turns"] = 0


def _after(stage: str, order: list[str]) -> list[str]:
    if stage in order:
        return order[order.index(stage) + 1 :]
    # Not in the order (turned off): what followed it in the default order.
    later = stages.ORDER[stages.ORDER.index(stage) + 1 :] if stage in stages.ORDER else []
    return [k for k in order if k in later] or order[-1:]


def _advance(s: dict[str, Any], cfg: FlowConfig) -> None:
    stage = s["stage"]
    rest = _after(stage, cfg.order)
    if stage == stages.PURPOSE:
        chosen = next((p for p in cfg.purposes if p["id"] == s.get("purpose")), None)
        jump = chosen.get("jump") if chosen else None
        if jump in rest:
            _enter(s, jump)
            return
    _enter(s, rest[0] if rest else stages.CLOSING)


def _limits(s: dict[str, Any], cfg: FlowConfig) -> tuple[int, int | None]:
    stage = s["stage"]
    if stage == stages.SELF_KINDNESS and s.get("branch") in ("weak", "none"):
        return _WEAK_SELF_KINDNESS_MIN, _WEAK_SELF_KINDNESS_MAX
    if stage in (stages.PURPOSE, stages.CLOSING):
        return 1, None
    return cfg.limits_for(stage)


def _purpose_from(confirmation: dict[str, Any] | None, cfg: FlowConfig) -> str:
    labels = (confirmation or {}).get("selected_labels") or []
    for p in cfg.purposes:
        if any(label in p["labels"].values() for label in labels):
            return p["id"]
    return "other"  # typed in their own words


def before_reply(
    session: ConversationSession,
    user_text: str | None,
    confirmation: dict[str, Any] | None,
    self_criticism_level: float,
    cfg: FlowConfig,
) -> dict[str, Any]:
    """Applies what the user just did; returns the state the reply is
    written in (also saved on the session)."""

    s = state(session, cfg)
    card = (confirmation or {}).get("card_type")
    stage = s["stage"]

    # Dismissing a stage's checkpoint card counts as skipping the stage: the
    # card is shown only once, so waiting for it would stall the conversation.
    dismissed = card in ("seb_summary", "plan_form") and not (confirmation or {}).get("fields")
    if card == "skip" or (dismissed and stage in (stages.LISTEN, stages.ACT)):
        if stage == stages.SELF_CHECK:
            s["branch"] = "none"
        if stage != stages.CLOSING:
            _advance(s, cfg)
    elif stage == stages.LISTEN and card == "seb_summary" and (confirmation or {}).get("fields"):
        _advance(s, cfg)
    elif stage == stages.PURPOSE and (user_text or card == PURPOSE_CARD):
        s["purpose"] = _purpose_from(confirmation if card == PURPOSE_CARD else None, cfg)
        _advance(s, cfg)
    elif stage == stages.ACT and card == "plan_form" and (confirmation or {}).get("fields"):
        _advance(s, cfg)
    elif user_text:
        s["turns"] = s.get("turns", 0) + 1
        _, most = _limits(s, cfg)
        if most is not None and s["turns"] >= most:
            if stage == stages.SELF_CHECK and not s.get("branch"):
                # No clear answer: fall back on the code-side keyword signal.
                s["branch"] = (
                    "strong" if self_criticism_level >= 0.5 else "weak" if self_criticism_level > 0 else "none"
                )
            _advance(s, cfg)

    session.flow_state = s
    return s


def after_reply(
    session: ConversationSession, signals: dict[str, Any], cfg: FlowConfig, summary_shown: bool = False
) -> None:
    """Applies the model's progress signals for the next turn.
    `summary_shown`: the listen summary was shown before this turn, so a
    stage_done here means the user confirmed it in their own words."""

    s = state(session, cfg)
    stage, turns = s["stage"], s.get("turns", 0)
    request = signals.get("user_request")
    if request == "end_today" and stage != stages.CLOSING:
        _enter(s, stages.CLOSING)
    elif request == "to_action" and stages.ACT in _after(stage, cfg.order):
        _enter(s, stages.ACT)
    elif stage == stages.SELF_CHECK:
        level = signals.get("self_criticism")
        if turns >= 1 and level in ("strong", "weak", "none"):
            s["branch"] = level
            _advance(s, cfg)
    elif stage == stages.LISTEN and summary_shown and signals.get("stage_done") is True:
        _advance(s, cfg)
    elif stage not in _USER_ENDED and signals.get("stage_done") is True and turns >= _limits(s, cfg)[0]:
        _advance(s, cfg)
    session.flow_state = s


def purpose_card(language: Language, cfg: FlowConfig) -> dict[str, Any]:
    return {
        "type": PURPOSE_CARD,
        "items": [{"id": p["id"], "label": cfg.purpose_label(p["id"], language)} for p in cfg.purposes],
    }


def purpose_note(s: dict[str, Any], language: Language, cfg: FlowConfig, sys: dict[str, str]) -> str:
    """For the prompt: what the user said they want from this conversation."""

    pid = s.get("purpose")
    if not pid or not sys["system.note_purpose"]:
        return ""
    what = cfg.purpose_label(pid, language) or (
        "见用户上一句话" if language == Language.ZH else "사용자의 앞선 말 참고"
    )
    return sys["system.note_purpose"].replace("{purpose}", what)


def branch_note(s: dict[str, Any], sys: dict[str, str]) -> str:
    if s["stage"] != stages.SELF_KINDNESS:
        return ""
    return sys["system.note_branch_strong" if s.get("branch") == "strong" else "system.note_branch_weak"]
