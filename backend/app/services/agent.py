"""The conversation agent, kept simple: the system prompt (+ the chosen
persona, + the crisis prompt when a crisis keyword is hit) and the recent
history go to the model, and the reply is streamed back. The wording and
parameters are all in app/services/agent_config.py.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Language, MessageRole, RiskLevel
from app.models.message import Message
from app.models.session import ConversationSession
from app.services import agent_config, llm, safety

AGENT_VERSION = "v3"

_REPLY_LANGUAGE = {
    Language.ZH: "【回复语言】一律用简体中文回复。",
    Language.KO: "【답변 언어】반드시 한국어로 답하세요.",
}


@dataclass
class Turn:
    """Everything decided before the reply is written."""

    messages: list[dict[str, str]]
    model: str
    risk: RiskLevel
    persona: str

    def meta(self) -> dict[str, Any]:
        return {"agent": AGENT_VERSION, "model": self.model, "persona": self.persona, "risk_level": self.risk.value}


def _system_prompt(persona: dict[str, Any], language: Language, crisis: bool, ending: bool) -> str:
    name = persona["name"].get(language.value) or next(iter(persona["name"].values()), "")
    parts = [
        agent_config.SYSTEM_PROMPT,
        f"【你这次的风格：{name}】{persona['prompt']}",
        _REPLY_LANGUAGE[language],
        agent_config.CRISIS_PROMPT if crisis else "",
        agent_config.ENDING_PROMPT if ending else "",
    ]
    return "\n\n".join(p.strip() for p in parts if p.strip())


async def prepare(
    db: AsyncSession, session: ConversationSession, user_text: str | None, ending: bool = False
) -> Turn:
    """Builds the reply's messages. Call after this turn's user message was
    added to `db`."""

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]))
        .order_by(Message.created_at)
    )
    history = list(result.scalars().all())
    # The user's message just added is the last one; it's sent separately.
    if user_text and history and history[-1].role == MessageRole.USER and history[-1].content == user_text:
        history = history[:-1]

    crisis = bool(user_text) and safety.is_crisis(user_text)
    persona = agent_config.persona(session.persona)
    n = agent_config.PARAMS["history_turns"]
    messages = [{"role": "system", "content": _system_prompt(persona, session.language, crisis, ending)}]
    messages += [{"role": m.role.value, "content": m.content} for m in history[-n:]]
    messages.append({"role": "user", "content": user_text or "（用户点了「结束对话」）"})
    return Turn(
        messages=messages,
        model=agent_config.model(),
        risk=RiskLevel.CRISIS if crisis else RiskLevel.NONE,
        persona=persona["id"],
    )


async def stream_reply(turn: Turn) -> AsyncIterator[str]:
    """The reply, piece by piece. Raises LLMUnavailable on a failed or
    empty reply."""

    got = False
    async for piece in llm.stream_text(turn.messages, turn.model, agent_config.PARAMS):
        got = got or bool(piece.strip())
        yield piece
    if not got:
        raise llm.LLMUnavailable("empty reply")
