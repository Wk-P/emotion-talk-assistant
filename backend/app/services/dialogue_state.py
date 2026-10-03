"""Core dialogue orchestrator (design principles 10.1, 10.4).

Responsibilities that MUST stay in code, not in a prompt:
  - risk screening and crisis routing (app/services/safety.py)
  - which flow's system prompt gets used (app/prompts/router.py)
  - merging a user's *confirmed* selections into session state

The LLM only ever produces the reply text and candidate suggestions for the
turn; it never decides safety routing or writes directly into confirmed_context.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import kst_iso
from app.models.enums import Language, MessageRole, RiskLevel
from app.models.message import Message
from app.models.resource import CrisisResource
from app.models.session import ConversationSession
from app.prompts import stages
from app.prompts.router import build_prompt
from app.services import flow, flow_config, safety
from app.services.llm import generate_turn
from app.services.model_settings import current_effort, current_model


# The only structured cards the model may attach, and only in their stage:
# the two flowchart checkpoints the user confirms/edits and can save to their
# records. The purpose card is added by code (flow.purpose_card), not the
# model. Enforced here rather than left to the prompt, because the model kept
# attaching option cards to nearly every reply and admin-edited prompt text
# can't override this. Options the user may pick from (emotion words,
# regulation methods) go in the reply text instead.
ALLOWED_CARDS_BY_STAGE = {stages.LISTEN: "seb_summary", stages.ACT: "plan_form"}
# The summary needs something to summarize: not before the user has said at
# least this many things.
MIN_USER_TURNS_FOR_SUMMARY = 3

_CRISIS_COPY = {
    Language.ZH: (
        "谢谢你愿意告诉我这些。这听起来很沉重，我想先确认一下你现在的安全状态——"
        "这部分超出了我能提供的支持范围，下面是一些经过核实的、可以立即联系的资源。"
    ),
    Language.KO: (
        "이렇게 말씀해 주셔서 고마워요. 지금 많이 힘드신 것 같아요. 먼저 지금 안전한 상태인지 확인하고 싶어요—"
        "이 부분은 제가 도울 수 있는 범위를 넘어서서, 지금 바로 연락할 수 있는 검증된 자원을 안내해 드릴게요."
    ),
}


@dataclass
class TurnResult:
    reply_text: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.NONE
    # The text actually sent to the LLM as "user" input this turn, when it
    # differs from the raw request body (e.g. a confirmation-only turn was
    # described in words for the model). None when no LLM call was made, or
    # when it's identical to the caller-supplied user_text. The API layer
    # persists this so later turns' history reconstruction still shows what
    # was confirmed — see app/api/chat.py.
    user_text_used: str | None = None
    # The stage this reply was written in (app/prompts/stages.py).
    stage: str | None = None
    # The model's progress signals (llm.SIGNAL_FIELDS), for flow.after_reply.
    signals: dict[str, Any] = field(default_factory=dict)
    # {prompt key: version} this reply was generated from (0 = code default,
    # see app/models/prompt.py). None for turns that use no editable prompt.
    prompt_versions: dict[str, int] | None = None
    # Which OpenAI model wrote this reply (None when no LLM call was made).
    model: str | None = None


async def _crisis_turn(db: AsyncSession, language: Language) -> TurnResult:
    country = "KR"  # participants are studying in Korea; primary resources are KR-based
    result = await db.execute(select(CrisisResource).where(CrisisResource.country == country))
    resources = result.scalars().all()
    candidates = [
        {
            "type": "crisis_resources",
            "items": [
                {
                    "id": r.id,
                    "label": r.name.get(language.value, r.name.get("ko", "")),
                    "description": r.description.get(language.value, r.description.get("ko", "")),
                    "contact": r.contact,
                    "url": r.url,
                    "verified_at": kst_iso(r.verified_at),
                }
                for r in resources
            ],
        }
    ]
    return TurnResult(reply_text=_CRISIS_COPY[language], candidates=candidates, risk_level=RiskLevel.CRISIS)


async def _load_messages(db: AsyncSession, session_id: str) -> list[Message]:
    # Includes this turn's user message: the API layer adds it before calling
    # handle_turn and the query autoflushes it.
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return [m for m in result.scalars().all() if m.role != MessageRole.SYSTEM]


def _history_for_llm(messages: list[Message], current_text: str, turns: int) -> list[dict[str, str]]:
    # `turns`: how many recent messages the model sees (admin-set, flow_config).
    recent = messages[-turns:]
    # generate_turn appends this turn's input itself; without dropping it here
    # the model saw the user's latest message twice and would apologise for
    # "not catching" what they'd just said.
    if recent and recent[-1].role == MessageRole.USER and recent[-1].content == current_text:
        recent = recent[:-1]
    return [{"role": m.role.value, "content": m.content} for m in recent]


def _cards_already_shown(messages: list[Message]) -> set[str]:
    return {
        c.get("type")
        for m in messages
        if m.role == MessageRole.ASSISTANT
        for c in (m.meta or {}).get("candidates", [])
        if isinstance(c, dict)
    }


def _filter_candidates(
    candidates: list[dict[str, Any]], messages: list[Message], stage: str
) -> list[dict[str, Any]]:
    """At most one card per reply, only the checkpoint of the current stage,
    and each checkpoint at most once per conversation (shown once is enough
    — if the user didn't confirm it, re-showing it every turn is just noise)."""

    shown = _cards_already_shown(messages)
    user_turns = sum(1 for m in messages if m.role == MessageRole.USER)
    for card in candidates:
        card_type = card.get("type") if isinstance(card, dict) else None
        if card_type != ALLOWED_CARDS_BY_STAGE.get(stage) or card_type in shown:
            continue
        if card_type == "seb_summary" and user_turns < MIN_USER_TURNS_FOR_SUMMARY:
            continue
        return [card]
    return []


# Tells the model which one-time checkpoints are already done, so it neither
# re-offers them (they'd be filtered anyway) nor refers to a card the user
# will never see ("下面是整理的小结…" with nothing below it).
_SHOWN_CARD_NOTES = {
    "seb_summary": {
        Language.ZH: "本次对话已经给用户看过「发生了什么—感受—应对」小结了，不要再整理小结，也不要在回复里提到小结。",
        Language.KO: "이번 대화에서 '상황-감정-대처' 요약은 이미 보여 주었어요. 다시 요약하지 말고, 답변에서 요약을 언급하지도 마세요.",
    },
    "plan_form": {
        Language.ZH: "本次对话已经给用户看过整理好的小计划了，不要再生成计划，也不要在回复里说「下面是计划」。",
        Language.KO: "이번 대화에서 정리한 작은 계획은 이미 보여 주었어요. 다시 만들지 말고, 답변에서 '아래 계획'이라고 말하지 마세요.",
    },
}


def _progress_note(
    messages: list[Message], state: dict[str, Any], cfg: flow_config.FlowConfig, language: Language
) -> str:
    shown = _cards_already_shown(messages)
    lines = [notes[language] for card_type, notes in _SHOWN_CARD_NOTES.items() if card_type in shown]
    lines += [note for note in (flow.purpose_note(state, language, cfg), flow.branch_note(state, language)) if note]
    if not lines:
        return ""
    header = "【当前进度】" if language == Language.ZH else "[현재 진행 상황]"
    return "\n\n---\n" + header + "\n" + "\n".join(f"- {line}" for line in lines)


def merge_confirmation(session: ConversationSession, confirmation: dict[str, Any]) -> None:
    """Deterministically folds a user-confirmed card back into session state.
    This is the ONLY place confirmed_context is written from candidate data —
    never from raw, unconfirmed LLM output (design principle: candidates only
    become facts once the user confirms/edits them)."""

    ctx = dict(session.confirmed_context or {})
    card_type = confirmation.get("card_type")
    selected = confirmation.get("selected_labels", [])
    custom = confirmation.get("custom_text")
    values = [*selected, *( [custom] if custom else [] )]

    if card_type == "emotion_options":
        ctx["emotions"] = list({*ctx.get("emotions", []), *values})
    elif card_type == "self_kindness_options" and values:
        ctx.setdefault("self_kindness_texts", []).append(values[0])
    elif card_type == "stabilization_options" and values:
        ctx.setdefault("stabilization_log", []).append(values[0])
    elif card_type == "recovery_action_options":
        ctx["recovery_actions"] = list({*ctx.get("recovery_actions", []), *values})
    elif card_type == "plan_form":
        ctx["recovery_plan"] = confirmation.get("fields", ctx.get("recovery_plan"))
    elif card_type == "seb_summary" and confirmation.get("fields"):
        ctx.setdefault("seb_entries", []).append(confirmation["fields"])
    elif card_type == flow.PURPOSE_CARD and values:
        ctx["purpose"] = values[0]

    session.confirmed_context = ctx


def _describe_confirmation(confirmation: dict[str, Any], language: Language) -> str | None:
    """Turns a confirmed card into a plain-language line the LLM can read as
    conversation input. Without this, a confirmation-only turn (no free text)
    left the model with no idea what the user actually picked — it only ever
    saw confirmed_context server-side, never in its own prompt/history."""

    card_type = confirmation.get("card_type")
    selected = confirmation.get("selected_labels") or []
    custom = confirmation.get("custom_text")
    fields = confirmation.get("fields")
    values = [*selected, *([custom] if custom else [])]

    if card_type == "end":
        return "(用户选择结束本次对话)" if language == Language.ZH else "(사용자가 이번 대화를 끝내기로 했어요)"
    if card_type == "skip":
        # Bottom-toolbar "skip" (design principle 8.2/10.5; the lead's
        # "跳过 → 跳过当前阶段"): flow.before_reply has already moved to the
        # next stage, so the model just carries on there.
        return "(用户选择跳过当前这一步)" if language == Language.ZH else "(사용자가 지금 단계를 건너뛰었어요)"
    if values:
        joined = "、".join(values) if language == Language.ZH else ", ".join(values)
        if language == Language.ZH:
            return f"(用户确认选择了：{joined})"
        return f"(사용자가 다음을 선택했어요: {joined})"
    if fields:
        joined = "; ".join(f"{k}: {v}" for k, v in fields.items() if v)
        if not joined:
            return None
        if language == Language.ZH:
            return f"(用户填写了：{joined})"
        return f"(사용자가 다음과 같이 작성했어요: {joined})"
    return None


async def handle_turn(
    db: AsyncSession,
    session: ConversationSession,
    user_text: str | None,
    confirmation: dict[str, Any] | None,
) -> TurnResult:
    language = session.language

    if confirmation:
        merge_confirmation(session, confirmation)

    risk = RiskLevel.NONE
    if user_text:
        risk = safety.screen_text(user_text)
        session.self_criticism_level = safety.bump_self_criticism(user_text, session.self_criticism_level)
        if risk == RiskLevel.CRISIS:
            return await _crisis_turn(db, language)

    confirmation_description = _describe_confirmation(confirmation, language) if confirmation else None
    synthetic_text = (
        user_text
        or confirmation_description
        or ("(已确认选择，请继续)" if language == Language.ZH else "(선택을 확인했어요, 계속해 주세요)")
    )
    ending = bool(confirmation and confirmation.get("card_type") == "end")
    # The stage is decided in code (app/services/flow.py); an overwhelmed
    # turn is answered with the stabilization prompt without leaving it.
    cfg = await flow_config.load(db)
    state = flow.state(session, cfg) if ending else flow.before_reply(
        session, user_text, confirmation, session.self_criticism_level, cfg
    )
    if ending:
        flow_key = stages.ENDING
    elif risk == RiskLevel.WATCH:
        flow_key = stages.STABILIZATION
    else:
        flow_key = state["stage"]

    result = await _continue_flow(
        db, session, synthetic_text=synthetic_text, flow_key=flow_key, state=state, cfg=cfg, risk=risk, ending=ending
    )
    if not ending and risk != RiskLevel.WATCH:
        flow.after_reply(session, result.signals, cfg)
    if not user_text:
        result.user_text_used = synthetic_text
    return result


async def _continue_flow(
    db: AsyncSession,
    session: ConversationSession,
    synthetic_text: str,
    flow_key: str,
    state: dict[str, Any],
    cfg: flow_config.FlowConfig,
    risk: RiskLevel = RiskLevel.NONE,
    ending: bool = False,
) -> TurnResult:
    system_prompt, prompt_versions = await build_prompt(db, flow_key, session.language)
    messages = await _load_messages(db, session.id)
    system_prompt += _progress_note(messages, state, cfg, session.language)
    history = _history_for_llm(messages, synthetic_text, cfg.history_turns)

    model = await current_model(db)
    effort = await current_effort(db)
    llm_response = await generate_turn(system_prompt, history, synthetic_text, model, effort=effort)
    candidates = [] if ending else _filter_candidates(llm_response.candidates, messages, flow_key)
    if flow_key == stages.PURPOSE and not ending:
        candidates = [flow.purpose_card(session.language, cfg)]
    return TurnResult(
        reply_text=llm_response.reply_text,
        candidates=candidates,
        risk_level=risk,
        stage=flow_key,
        signals=llm_response.signals,
        prompt_versions=prompt_versions,
        model=model,
    )
