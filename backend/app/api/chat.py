import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user_required, get_owned_session
from app.db.session import async_session_maker, get_db
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.user import User
from app.schemas.chat import (
    ChatStreamRequest,
    PersonaChoice,
    PersonaItem,
    PersonaList,
    RatingRequest,
)
from app.services import agent, agent_config
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _open_session(db: AsyncSession, session_id: str, user: User) -> ConversationSession:
    session = await get_owned_session(session_id, db, user)
    if session.ended_at:
        # The user chose "结束对话"; an ended conversation is read-only.
        raise HTTPException(status_code=409, detail="session ended")
    return session


def _add_user_message(db: AsyncSession, session: ConversationSession, text: str) -> str:
    message_id = str(uuid.uuid4())
    db.add(Message(id=message_id, session_id=session.id, role=MessageRole.USER, content=text))
    session.participated = True
    return message_id


def _add_reply(db: AsyncSession, session: ConversationSession, text: str, turn: agent.Turn, end: bool) -> str:
    message_id = str(uuid.uuid4())
    db.add(Message(id=message_id, session_id=session.id, role=MessageRole.ASSISTANT, content=text, meta=turn.meta()))
    if end:
        # Only marks the conversation finished — the turns stay.
        session.ended_at = datetime.now(timezone.utc)
    db.add(session)
    return message_id


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> StreamingResponse:
    """One turn, streamed as server-sent events: `delta` {text} as the reply
    is written, then `done` {user_message_id, assistant_message_id,
    risk_level}, or `error` {reason}. Nothing is saved unless the reply
    finished, so the client can simply retry."""

    if not payload.message and not payload.end:
        raise HTTPException(status_code=422, detail="message or end required")
    await _open_session(db, payload.session_id, user)

    async def events():
        # Its own database session: the request's closes when the response starts.
        async with async_session_maker() as sdb:
            session = await _open_session(sdb, payload.session_id, user)
            user_message_id = _add_user_message(sdb, session, payload.message) if payload.message else None
            parts: list[str] = []
            try:
                turn = await agent.prepare(sdb, session, payload.message, ending=payload.end)
                async for piece in agent.stream_reply(turn):
                    parts.append(piece)
                    yield _event("delta", {"text": piece})
            except LLMUnavailable as e:
                await sdb.rollback()
                yield _event("error", {"reason": e.reason})
                return
            assistant_message_id = _add_reply(sdb, session, "".join(parts).strip(), turn, payload.end)
            await sdb.commit()
            yield _event(
                "done",
                {
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message_id,
                    "risk_level": turn.risk.value,
                },
            )

    # No buffering by proxies (Cloudflare / nginx), so pieces arrive as written.
    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.put("/messages/{message_id}/rating", status_code=204)
async def rate_reply(
    message_id: str,
    payload: RatingRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> None:
    """The 0-5 rating beside an AI reply, kept on the reply (meta.rating)."""

    message = await db.get(Message, message_id)
    if not message or message.role != MessageRole.ASSISTANT:
        raise HTTPException(status_code=404, detail="message not found")
    await get_owned_session(message.session_id, db, user)
    message.meta = {**(message.meta or {}), "rating": payload.rating, "rated_at": datetime.now(timezone.utc).isoformat()}
    flag_modified(message, "meta")
    await db.commit()


@router.get("/personas", response_model=PersonaList)
async def list_personas(_: User = Depends(get_current_user_required)) -> PersonaList:
    return PersonaList(
        personas=[PersonaItem(id=p["id"], name=p["name"], intro=p["intro"]) for p in agent_config.PERSONAS],
        default=agent_config.DEFAULT_PERSONA,
    )


@router.put("/sessions/{session_id}/persona", status_code=204)
async def choose_persona(
    payload: PersonaChoice,
    db: AsyncSession = Depends(get_db),
    session: ConversationSession = Depends(get_owned_session),
) -> None:
    """Later replies use this persona (None = the default)."""

    if payload.persona and payload.persona not in {p["id"] for p in agent_config.PERSONAS}:
        raise HTTPException(status_code=422, detail="unknown persona")
    session.persona = payload.persona
    await db.commit()
