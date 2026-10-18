"""Core dialogue orchestrator (design principles 10.1, 10.4).

Responsibilities that MUST stay in code, not in a prompt:
  - risk screening and crisis routing (app/services/safety.py)
  - which flow's system prompt gets used (app/prompts/router.py)
  - merging a user's *confirmed* selections into session state

The LLM only ever produces the reply text and candidate suggestions for the
turn; it never decides safety routing or writes directly into confirmed_context.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import kst_iso
from app.models.enums import Language, MessageRole, RiskLevel
from app.models.message import Message
from app.models.resource import CrisisResource
from app.models.session import ConversationSession
from app.prompts import registry, stages
from app.prompts.router import build_prompt
from app.services import ai_params, flow, flow_config, safety
from app.services.llm import generate_turn
from app.services.model_settings import current_effort, current_model


# The only structured cards the model may attach, and only in their stage
# (admin-set, flow_config.card_steps): the two flowchart checkpoints the user
# confirms/edits and can save to their records. Enforced here rather than left to
# the prompt, because the model kept attaching option cards to nearly every
# reply. Options the user may pick from go in the reply text instead.
# The minimum number of things the user has said before the summary may show
# is admin-set (flow_config.summary_min_turns), as are the crisis reply text
# and the screening word lists.


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
    # The listen summary was shown before this turn (flow.after_reply).
    summary_shown: bool = False
    # What the program decided this turn, for the admin transcript:
    # [{"zh": ..., "ko": ...}] (see _format_log).
    flow_log: list[dict[str, str]] = field(default_factory=list)


# Card names in the admin log.
_CARD_NAMES = {
    "seb_summary": ("总结卡片", "요약 카드"),
    "plan_form": ("行动计划卡片", "행동 계획 카드"),
    "kindness_form": ("友善的话卡片", "따뜻한 말 카드"),
    "skip": ("跳过", "건너뛰기"),
    "end": ("结束对话", "대화 끝내기"),
    "emotion_options": ("情绪选项", "감정 선택지"),
    "self_kindness_options": ("自我友善选项", "자기 친절 선택지"),
    "stabilization_options": ("平静下来选项", "진정 선택지"),
    "recovery_action_options": ("恢复行动选项", "회복 행동 선택지"),
}


def _card_name(card: Any, i: int) -> str:
    return _CARD_NAMES.get(str(card), (str(card), str(card)))[i]


async def _format_log(db: AsyncSession, log: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Fills in step names ("{k:<key>}") in each admin language."""

    modules = {m.key: m for m in await registry.load_modules(db)}

    def fill(text: str, language: Language) -> str:
        def name(match: re.Match[str]) -> str:
            m = modules.get(match.group(1))
            title = m.title(language) if m else match.group(1)
            return f"「{title}」" if language == Language.ZH else f'"{title}"'

        return re.sub(r"\{k:([^}]+)\}", name, text)

    return [{"zh": fill(zh, Language.ZH), "ko": fill(ko, Language.KO)} for zh, ko in log]


async def _crisis_turn(db: AsyncSession, language: Language, cfg: flow_config.FlowConfig) -> TurnResult:
    query = select(CrisisResource)
    if cfg.crisis_country:  # admin-set; participants are studying in Korea, so KR by default
        query = query.where(CrisisResource.country == cfg.crisis_country)
    result = await db.execute(query)
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
    return TurnResult(reply_text=cfg.crisis_text(language), candidates=candidates, risk_level=RiskLevel.CRISIS)


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
    candidates: list[dict[str, Any]], messages: list[Message], stage: str, cfg: flow_config.FlowConfig
) -> list[dict[str, Any]]:
    """At most one card per reply, only the checkpoint of the current stage,
    and each checkpoint at most once per conversation (shown once is enough
    — if the user didn't confirm it, re-showing it every turn is just noise)."""

    shown = _cards_already_shown(messages)
    user_turns = sum(1 for m in messages if m.role == MessageRole.USER)
    for card in candidates:
        card_type = card.get("type") if isinstance(card, dict) else None
        if card_type != cfg.card_for(stage) or card_type in shown:
            continue
        if card_type == "seb_summary" and user_turns < cfg.summary_min_turns:
            continue
        return [card]
    return []


# Tells the model which one-time checkpoints are already done, so it neither
# re-offers them (they'd be filtered anyway) nor refers to a card the user
# will never see. Wording: admin page "程序附加说明" (app/prompts/system.py).
_SHOWN_CARD_NOTES = {
    "seb_summary": "system.note_summary_shown",
    "plan_form": "system.note_plan_shown",
    "kindness_form": "system.note_kindness_shown",
}


def _progress_note(
    messages: list[Message],
    state: dict[str, Any],
    cfg: flow_config.FlowConfig,
    language: Language,
    flow_key: str,
    sys: dict[str, str],
) -> str:
    shown = _cards_already_shown(messages)
    lines = [sys[key] for card_type, key in _SHOWN_CARD_NOTES.items() if card_type in shown]
    if flow_key == cfg.card_steps.get("seb_summary") and "seb_summary" in shown:
        # The user may confirm the summary by typing instead of using the
        # card; the model reports it as stage_done and flow.after_reply moves on.
        to_purpose = flow._after(flow_key, cfg.order)[:1] == [stages.PURPOSE]
        lines.append(sys["system.note_listen_confirm" if to_purpose else "system.note_listen_confirm_other"])
        if to_purpose:
            lines.append(sys["system.note_no_purpose_buttons"])
    elif flow_key == stages.PURPOSE:
        # Prompts written when there were purpose buttons may still mention them.
        lines.append(sys["system.note_no_purpose_buttons"])
    lines += [flow.purpose_note(state, language, cfg, sys), flow.branch_note(state, sys), flow.jump_note(state, sys)]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "\n\n---\n" + "\n".join(p for p in (sys["system.note_header"], *(f"- {line}" for line in lines)) if p)


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
    elif card_type == "kindness_form" and (confirmation.get("fields") or {}).get("text"):
        ctx.setdefault("self_kindness_texts", []).append(confirmation["fields"]["text"])
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

    cfg = await flow_config.load(db)
    risk = RiskLevel.NONE
    if user_text:
        risk = safety.screen_text(user_text, cfg.keywords)
        session.self_criticism_level = safety.bump_self_criticism(
            user_text, session.self_criticism_level, cfg.keywords, cfg.criticism
        )
        if risk == RiskLevel.CRISIS:
            result = await _crisis_turn(db, language, cfg)
            result.flow_log = await _format_log(
                db, [("发现危机关键词：不走步骤，直接回复危机求助信息", "위기 키워드 감지: 단계를 건너뛰고 위기 도움 안내로 답해요")]
            )
            return result

    confirmation_description = _describe_confirmation(confirmation, language) if confirmation else None
    synthetic_text = (
        user_text
        or confirmation_description
        or ("(已确认选择，请继续)" if language == Language.ZH else "(선택을 확인했어요, 계속해 주세요)")
    )
    ending = bool(confirmation and confirmation.get("card_type") == "end")
    log: list[tuple[str, str]] = []
    if user_text:
        log.append((f"安全检查：{'情绪特别激动' if risk == RiskLevel.WATCH else '正常'}；自我批评程度 {round(session.self_criticism_level * 100)}", f"안전 확인: {'많이 격해 보임' if risk == RiskLevel.WATCH else '정상'}; 자기비판 정도 {round(session.self_criticism_level * 100)}"))
    if confirmation:
        card = confirmation.get("card_type")
        log.append((f"用户操作了卡片：{_card_name(card, 0)}", f"사용자의 카드 조작: {_card_name(card, 1)}"))
    # The stage is decided in code (app/services/flow.py); an overwhelmed
    # turn is answered with the stabilization prompt without leaving it.
    state = flow.state(session, cfg) if ending else flow.before_reply(
        session, user_text, confirmation, session.self_criticism_level, cfg, log
    )
    # Admins may turn ending / stabilization off: the current step answers.
    # Which step (if any) answers these is admin-set.
    if ending and cfg.usable(cfg.ending_step):
        flow_key = cfg.ending_step
        log.append((f"用户点了「结束对话」：这次由 {{k:{flow_key}}} 回复，之后对话锁定", f"사용자가 \"대화 끝내기\"를 눌렀어요: {{k:{flow_key}}}이(가) 답하고 대화가 잠겨요"))
    elif risk == RiskLevel.WATCH and cfg.usable(cfg.stabilize_step):
        flow_key = cfg.stabilize_step
        log.append((f"情绪特别激动：这一轮临时由 {{k:{flow_key}}} 回复，步骤不变", f"많이 격해 보여요: 이번에만 {{k:{flow_key}}}이(가) 답하고 단계는 그대로예요"))
    else:
        flow_key = state["stage"]
    log.append((f"本次回复使用：{{k:{flow_key}}}", f"이번 답변 단계: {{k:{flow_key}}}"))

    result = await _continue_flow(
        db, session, synthetic_text=synthetic_text, flow_key=flow_key, state=state, cfg=cfg, risk=risk, ending=ending
    )
    if result.candidates:
        log.append((
            f"附带卡片：{'、'.join(_card_name(c.get('type'), 0) for c in result.candidates)}",
            f"함께 보낸 카드: {', '.join(_card_name(c.get('type'), 1) for c in result.candidates)}",
        ))
    if not ending and risk != RiskLevel.WATCH:
        flow.after_reply(session, result.signals, cfg, summary_shown=result.summary_shown, log=log)
        nxt = (session.flow_state or {}).get("stage")
        if nxt:
            log.append((f"下一轮将从 {{k:{nxt}}} 开始", f"다음 차례는 {{k:{nxt}}}에서 시작해요"))
    result.flow_log = await _format_log(db, log)
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
    system_prompt, prompt_versions = await build_prompt(
        db, flow_key, session.language, triggered=flow_key != state["stage"], card=cfg.card_for(flow_key)
    )
    messages = await _load_messages(db, session.id)
    sys = await registry.system_texts(db, session.language)
    # Progress notes are the program's: they go with its message, the first.
    system_prompt[0] += _progress_note(messages, state, cfg, session.language, flow_key, sys)
    history = _history_for_llm(messages, synthetic_text, cfg.history_turns)

    model = await current_model(db)
    effort = await current_effort(db)
    params = await ai_params.load(db)
    llm_response = await generate_turn(system_prompt, history, synthetic_text, model, effort=effort, params=params)
    candidates = [] if ending else _filter_candidates(llm_response.candidates, messages, flow_key, cfg)
    return TurnResult(
        reply_text=llm_response.reply_text,
        candidates=candidates,
        risk_level=risk,
        stage=flow_key,
        signals=llm_response.signals,
        prompt_versions=prompt_versions,
        model=model,
        summary_shown="seb_summary" in _cards_already_shown(messages),
    )
