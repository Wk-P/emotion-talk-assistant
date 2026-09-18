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

HISTORY_TURNS = 12  # most recent messages included as LLM context

_DISCLAIMER = {
    Language.ZH: (
        "在开始之前先说明一下：这是一个帮助你梳理情绪、练习自我友善的陪伴工具，"
        "不是心理咨询师，不能做诊断或治疗；如果你正处于危险状态，请优先联系专业机构或信任的人。"
    ),
    Language.KO: (
        "시작하기 전에 안내드릴게요: 이 도구는 감정을 정리하고 자기친절을 연습하도록 돕는 동반자이며, "
        "전문 상담사가 아니라 진단이나 치료를 할 수 없어요. 만약 지금 위험한 상황이라면 "
        "전문 기관이나 믿을 수 있는 사람에게 먼저 연락해 주세요."
    ),
}

_INTENT_OPTION_COPY = {
    Language.ZH: {
        "reply_text": "在开始之前，想先了解一下：你现在最需要的是什么？",
        "items": [
            {"id": "vent", "label": "只是想说说 / 倾诉"},
            {"id": "organize", "label": "想整理一下自己的情绪"},
            {"id": "stabilize", "label": "现在情绪有点乱，想先稳定下来"},
            {"id": "information", "label": "想了解一些信息或资源"},
            {"id": "method", "label": "想找找应对的方法"},
        ],
    },
    Language.KO: {
        "reply_text": "시작하기 전에 먼저 여쭤볼게요. 지금 가장 필요한 게 무엇인가요?",
        "items": [
            {"id": "vent", "label": "그냥 이야기하고 싶어요"},
            {"id": "organize", "label": "감정을 정리하고 싶어요"},
            {"id": "stabilize", "label": "지금 마음이 어지러워요, 먼저 안정시키고 싶어요"},
            {"id": "information", "label": "정보나 자원을 알고 싶어요"},
            {"id": "method", "label": "대처 방법을 찾고 싶어요"},
        ],
    },
}

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


def _intent_from_id(value: str | None) -> DialogueIntent | None:
    try:
        return DialogueIntent(value) if value else None
    except ValueError:
        return None


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


async def _load_recent_history(db: AsyncSession, session_id: str) -> list[dict[str, str]]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURNS)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": m.role.value, "content": m.content} for m in rows if m.role != MessageRole.SYSTEM]


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

    if card_type == "intent_options" and selected:
        ctx["last_intent"] = selected[0]
    elif card_type == "emotion_options":
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

    if card_type == "intent_options":
        return None  # handled by the intent_options branch itself, no LLM turn yet
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

    ctx = session.confirmed_context or {}
    if not ctx.get("last_intent"):
        # Covers both the very first turn (no user_text yet, deterministic —
        # no LLM call) and any later turn where the user still hasn't picked
        # an intent (e.g. they replied before confirming the card).
        copy = _INTENT_OPTION_COPY[language]
        reply_text = copy["reply_text"]
        if not ctx.get("disclaimer_shown"):
            # Modified_Log.md "系统提示：开始之前加入免责声明" — sent once, verbatim,
            # by code rather than left to the model (design principle 8.1).
            reply_text = f"{_DISCLAIMER[language]}\n\n{reply_text}"
            ctx = {**ctx, "disclaimer_shown": True}
            session.confirmed_context = ctx
        return TurnResult(
            reply_text=reply_text,
            candidates=[{"type": "intent_options", "items": copy["items"]}],
        )

    confirmation_description = _describe_confirmation(confirmation, language) if confirmation else None
    synthetic_text = (
        user_text
        or confirmation_description
        or ("(已确认选择，请继续)" if language == Language.ZH else "(선택을 확인했어요, 계속해 주세요)")
    )
    maybe_intent = _intent_from_id(user_text) if user_text and user_text.startswith("intent:") else None
    effective_intent = (
        DialogueIntent.STABILIZE
        if risk == RiskLevel.WATCH
        else maybe_intent or _intent_from_id(ctx.get("last_intent")) or DialogueIntent.VENT
    )

    result = await _continue_flow(
        db, session, synthetic_text=synthetic_text, forced_intent=effective_intent, risk=risk
    )
    if not user_text:
        result.user_text_used = synthetic_text
    return result


async def _continue_flow(
    db: AsyncSession,
    session: ConversationSession,
    synthetic_text: str,
    forced_intent: DialogueIntent | None = None,
    risk: RiskLevel = RiskLevel.NONE,
) -> TurnResult:
    ctx = session.confirmed_context or {}
    intent = forced_intent or _intent_from_id(ctx.get("last_intent")) or DialogueIntent.VENT
    system_prompt = build_prompt(intent, session.language, session.self_criticism_level)
    history = await _load_recent_history(db, session.id)

    llm_response = await generate_turn(system_prompt, history, synthetic_text)
    return TurnResult(
        reply_text=llm_response.reply_text,
        candidates=llm_response.candidates,
        risk_level=risk,
        intent=intent,
    )
