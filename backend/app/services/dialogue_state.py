"""Core dialogue orchestrator (design principles 10.1, 10.4).

Responsibilities that MUST stay in code, not in a prompt:
  - risk screening and crisis routing (app/services/safety.py)
  - which flow's system prompt gets used (app/prompts/router.py)
  - merging a user's *confirmed* selections into session state

The LLM only ever produces the reply text and candidate suggestions for the
turn; it never decides safety routing or writes directly into confirmed_context.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timefmt import kst_iso
from app.models.enums import DialogueIntent, Language, MessageRole, RiskLevel
from app.models.message import Message
from app.models.resource import CrisisResource
from app.models.session import ConversationSession
from app.prompts.router import build_prompt
from app.services import safety
from app.services.llm import LLMUnavailable, analyze_turn, generate_turn
from app.services.model_settings import current_effort, current_model

logger = logging.getLogger(__name__)

HISTORY_TURNS = 12  # most recent messages included as LLM context

# The only structured cards that may reach the user — the two flowchart
# checkpoints the user confirms/edits and can save to their records. Pick-list
# cards (emotion words, methods, encouragement lines) are never shown: the
# research team's rule is that the AI asks open questions without offering
# options. Enforced here rather than left to the prompt, because the model
# kept attaching option cards to nearly every reply and admin-edited prompt
# text can't override this.
ALLOWED_CARD_TYPES = {"seb_summary", "plan_form"}
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
    intent: DialogueIntent | None = None
    # {prompt key: version} this reply was generated from (0 = code default,
    # see app/models/prompt.py). None for turns that use no editable prompt.
    prompt_versions: dict[str, int] | None = None
    # Which OpenAI model wrote this reply (None when no LLM call was made).
    model: str | None = None
    # Set only on the turn the analysis pass ran; stored in the message meta
    # and reused from there by later turns (see _latest_analysis).
    analysis: dict[str, Any] | None = None


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


def _history_for_llm(messages: list[Message], current_text: str) -> list[dict[str, str]]:
    recent = messages[-HISTORY_TURNS:]
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


def _filter_candidates(candidates: list[dict[str, Any]], messages: list[Message]) -> list[dict[str, Any]]:
    """At most one card per reply, only an allowed checkpoint type, and each
    checkpoint at most once per conversation (shown once is enough — if the
    user didn't confirm it, re-showing it every turn is just noise)."""

    shown = _cards_already_shown(messages)
    user_turns = sum(1 for m in messages if m.role == MessageRole.USER)
    for card in candidates:
        card_type = card.get("type") if isinstance(card, dict) else None
        if card_type not in ALLOWED_CARD_TYPES or card_type in shown:
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


def _progress_note(messages: list[Message], language: Language) -> str:
    shown = _cards_already_shown(messages)
    lines = [notes[language] for card_type, notes in _SHOWN_CARD_NOTES.items() if card_type in shown]
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
    elif card_type == "seb_summary":
        ctx.setdefault("seb_entries", []).append(confirmation.get("fields", {}))

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
        # Bottom-toolbar "skip" (design principle 8.2/10.5): distinct from a
        # generic confirmation-only continue so the model doesn't try to act
        # on a choice that was never made, and doesn't repeat the same
        # question verbatim.
        return "(用户选择跳过这个问题，请换一个方向继续)" if language == Language.ZH else "(사용자가 이 질문을 건너뛰었어요. 다른 방향으로 이어가 주세요)"
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


_CLOSING_INSTRUCTION = {
    Language.ZH: (
        "\n\n---\n【本轮：用户选择结束对话】\n"
        "用两三句话温和地结束这次对话：感谢用户愿意分享，简单肯定他今天说出来的东西"
        "（只提他真正说过的内容），告诉他需要时随时可以再来。不要提问，不要给建议或选项，"
        "candidates 给空数组。"
    ),
    Language.KO: (
        "\n\n---\n[이번 차례: 사용자가 대화를 끝내기로 했어요]\n"
        "두세 문장으로 따뜻하게 대화를 마무리하세요: 이야기해 준 것에 고마움을 전하고, 오늘 꺼내 놓은 이야기를 "
        "(실제로 말한 내용만) 간단히 인정해 주고, 필요할 때 언제든 다시 와도 된다고 알려 주세요. "
        "질문하지 말고, 조언이나 선택지를 주지 말고, candidates는 빈 배열로 두세요."
    ),
}


# Analysis pass — documents/02_内容与需求/Modified_Log.md "根据设计原理的修正":
# once the user has confirmed the situation-emotion-behavior summary, code
# first sorts out what is known (_rough_summary), then one extra model call
# analyses it along design principles 1-3 (documents/01_研究资料/최종설계원리2.pdf),
# and the reply is written with that analysis in hand. Runs once per
# conversation; later turns reuse the stored result. The analysis is the
# model's guess, never shown to the user and never written into
# confirmed_context (only user-confirmed data goes there).
_ANALYSIS_INSTRUCTION = {
    Language.ZH: (
        "【内部分析任务：这次不要回复用户】\n"
        "用户已经确认了下面这份整理。请根据整段对话，按三条设计原理做分析：\n"
        "1. 情绪与情境：用户有哪些情绪（可能同时有几种）、大概多强烈，与哪些具体情境相连；\n"
        "2. 想法与解释：困难的原因分别在个人、关系、环境、文化适应哪些方面；哪些是实际发生的事、哪些是用户的解释；"
        "不要把环境或文化带来的困难归成用户个人的问题；\n"
        "3. 价值与目标：用户在意的是什么、留学想达成什么，现在的做法和这些目标的关系。\n"
        "用户没说过的内容不要编，写「未知」。只输出一个 JSON 对象，字段用简体中文："
        '{"emotions": [string], "intensity": string, "causes": {"personal": string, "relationship": string, '
        '"environment": string, "acculturation": string}, "facts": [string], "interpretations": [string], '
        '"needs_values": [string], "self_criticism": string, "next_focus": string}。'
        "next_focus 写接下来对话最值得一起探索的一点。\n\n"
    ),
    Language.KO: (
        "[내부 분석 작업: 이번에는 사용자에게 답하지 마세요]\n"
        "사용자가 아래 정리를 확인했어요. 전체 대화를 바탕으로 세 가지 설계원리에 따라 분석하세요:\n"
        "1. 감정과 상황: 사용자의 감정(여러 가지일 수 있음)과 대략적인 강도, 그리고 연결된 구체적 상황;\n"
        "2. 생각과 해석: 어려움의 원인이 개인, 관계, 환경, 문화적응 중 어디에 있는지; 실제로 일어난 일과 사용자의 해석 구분; "
        "환경이나 문화에서 오는 어려움을 사용자 개인의 문제로 돌리지 마세요;\n"
        "3. 가치와 목표: 사용자가 중요하게 여기는 것, 유학에서 이루고 싶은 것, 지금의 행동과 그 목표의 관계.\n"
        "사용자가 말하지 않은 내용은 지어내지 말고 '알 수 없음'이라고 쓰세요. JSON 객체 하나만 출력하고 내용은 한국어로 쓰세요: "
        '{"emotions": [string], "intensity": string, "causes": {"personal": string, "relationship": string, '
        '"environment": string, "acculturation": string}, "facts": [string], "interpretations": [string], '
        '"needs_values": [string], "self_criticism": string, "next_focus": string}. '
        "next_focus에는 앞으로 함께 탐색할 가장 중요한 한 가지를 쓰세요.\n\n"
    ),
}

_ANALYSIS_NOTE_HEADER = {
    Language.ZH: (
        "【内部分析（只供你理解用户，不要直接念给用户，也不要提到「分析」；都是暂定的推测，"
        "需要用到时用确认的语气向用户求证）】\n"
    ),
    Language.KO: (
        "[내부 분석 (사용자를 이해하기 위한 참고용이에요. 그대로 읽어 주거나 '분석'이라고 언급하지 마세요. "
        "모두 잠정적인 추측이니 활용할 때는 확인하는 말투로 사용자에게 물어보세요)]\n"
    ),
}


def _latest_analysis(messages: list[Message]) -> dict[str, Any] | None:
    for m in reversed(messages):
        if m.role == MessageRole.ASSISTANT and (m.meta or {}).get("analysis"):
            return m.meta["analysis"]
    return None


def _rough_summary(session: ConversationSession, risk: RiskLevel, language: Language) -> str:
    """What code already knows, handed to the analysis call: the summary the
    user confirmed (last one wins) plus the code-side screening signals."""

    entry = ((session.confirmed_context or {}).get("seb_entries") or [{}])[-1]
    level = session.self_criticism_level
    if language == Language.ZH:
        criticism = "明显" if level >= 0.5 else "有一些" if level > 0 else "未发现"
        return (
            "【程序整理（用户已确认）】\n"
            f"- 发生了什么：{entry.get('situation') or '未知'}\n"
            f"- 当时的感受：{entry.get('emotion') or '未知'}\n"
            f"- 当时怎么应对：{entry.get('behavior') or '未知'}\n"
            f"- 自我批评的说法：{criticism}\n"
            f"- 情绪是否激动：{'是' if risk == RiskLevel.WATCH else '否'}"
        )
    criticism = "뚜렷함" if level >= 0.5 else "약간 있음" if level > 0 else "발견되지 않음"
    return (
        "[프로그램 정리 (사용자 확인 완료)]\n"
        f"- 무슨 일이 있었는지: {entry.get('situation') or '알 수 없음'}\n"
        f"- 그때의 감정: {entry.get('emotion') or '알 수 없음'}\n"
        f"- 그때 어떻게 대처했는지: {entry.get('behavior') or '알 수 없음'}\n"
        f"- 자기비판적 표현: {criticism}\n"
        f"- 감정이 격한 상태인지: {'예' if risk == RiskLevel.WATCH else '아니요'}"
    )


def _analysis_note(analysis: dict[str, Any], language: Language) -> str:
    return _ANALYSIS_NOTE_HEADER[language] + json.dumps(analysis, ensure_ascii=False, indent=1)


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

    # There is no fixed "what do you need?" step any more — the common
    # principle "确认对话目的" (app/prompts/principles.py) tells the AI to
    # work that out conversationally instead. Routing stays code-controlled
    # (never left to the model): self-criticism and the WATCH risk level can
    # still steer the flow below; absent either, every conversation starts
    # in the general exploration flow.
    confirmation_description = _describe_confirmation(confirmation, language) if confirmation else None
    synthetic_text = (
        user_text
        or confirmation_description
        or ("(已确认选择，请继续)" if language == Language.ZH else "(선택을 확인했어요, 계속해 주세요)")
    )
    # Flowchart order, decided in code: overwhelmed → stabilize first;
    # otherwise explore the experience and emotions (steps 6-7) until the
    # user confirms the situation-emotion-behavior summary, then move on to
    # practical next steps (step 10). The self-criticism check (step 8) can
    # still divert either of the latter to self-kindness (step 9) — see
    # app/prompts/router.flow_key_for.
    if risk == RiskLevel.WATCH:
        effective_intent = DialogueIntent.STABILIZE
    elif (session.confirmed_context or {}).get("seb_entries"):
        effective_intent = DialogueIntent.METHOD
    else:
        effective_intent = DialogueIntent.VENT

    ending = bool(confirmation and confirmation.get("card_type") == "end")
    result = await _continue_flow(
        db, session, synthetic_text=synthetic_text, intent=effective_intent, risk=risk, ending=ending
    )
    if not user_text:
        result.user_text_used = synthetic_text
    return result


async def _continue_flow(
    db: AsyncSession,
    session: ConversationSession,
    synthetic_text: str,
    intent: DialogueIntent,
    risk: RiskLevel = RiskLevel.NONE,
    ending: bool = False,
) -> TurnResult:
    system_prompt, prompt_versions = await build_prompt(db, intent, session.language, session.self_criticism_level)
    messages = await _load_messages(db, session.id)
    system_prompt += _progress_note(messages, session.language)
    if ending:
        system_prompt += _CLOSING_INSTRUCTION[session.language]
    history = _history_for_llm(messages, synthetic_text)

    model = await current_model(db)
    effort = await current_effort(db)
    analysis = _latest_analysis(messages)
    new_analysis = None
    if analysis is None and not ending and (session.confirmed_context or {}).get("seb_entries"):
        instruction = _ANALYSIS_INSTRUCTION[session.language] + _rough_summary(session, risk, session.language)
        try:
            new_analysis = await analyze_turn(system_prompt, history, synthetic_text, instruction, model, effort)
        except LLMUnavailable:
            # The reply below can still be written without it; the next turn retries.
            logger.warning("analysis pass failed; replying without it")
        analysis = new_analysis
    tail = _analysis_note(analysis, session.language) if analysis else None

    llm_response = await generate_turn(system_prompt, history, synthetic_text, model, tail=tail, effort=effort)
    candidates = [] if ending else _filter_candidates(llm_response.candidates, messages)
    return TurnResult(
        reply_text=llm_response.reply_text,
        candidates=candidates,
        risk_level=risk,
        intent=intent,
        prompt_versions=prompt_versions,
        model=model,
        analysis=new_analysis,
    )
