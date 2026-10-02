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

from app.models.enums import DialogueIntent, Language, MessageRole, RiskLevel
from app.models.message import Message
from app.models.resource import CrisisResource
from app.models.session import ConversationSession
from app.prompts.router import build_prompt
from app.services import safety
from app.services.llm import generate_turn
from app.services.model_settings import current_model

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
                    "verified_at": r.verified_at.isoformat(),
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
    if ending:
        system_prompt += _CLOSING_INSTRUCTION[session.language]
    messages = await _load_messages(db, session.id)
    history = _history_for_llm(messages, synthetic_text)

    model = await current_model(db)
    llm_response = await generate_turn(system_prompt, history, synthetic_text, model)
    candidates = [] if ending else _filter_candidates(llm_response.candidates, messages)
    return TurnResult(
        reply_text=llm_response.reply_text,
        candidates=candidates,
        risk_level=risk,
        intent=intent,
        prompt_versions=prompt_versions,
        model=model,
    )
