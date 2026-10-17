from typing import Any

from pydantic import BaseModel

from app.models.enums import Language, RiskLevel


class SessionCreateRequest(BaseModel):
    language: Language = Language.ZH


class SessionResponse(BaseModel):
    session_id: str
    language: Language


class SessionHistoryItem(BaseModel):
    session_id: str
    language: Language
    created_at: str
    ended_at: str | None
    message_count: int
    # When the last message was sent (created_at if none yet): the list is
    # ordered by it, so a conversation continued today sits on top.
    last_active_at: str
    # The user's first message, cut short — a recognisable name for the list.
    title: str


class HistoryMessageItem(BaseModel):
    role: str
    content: str
    created_at: str


class SessionSyncResponse(BaseModel):
    # User/assistant messages after the first `after` ones, how many there
    # are in all, and whether the conversation was ended (maybe elsewhere).
    messages: list[HistoryMessageItem]
    total: int
    ended: bool


class ConfirmationPayload(BaseModel):
    card_type: str
    selected_labels: list[str] = []
    custom_text: str | None = None
    fields: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str | None = None
    confirmation: ConfirmationPayload | None = None


class CandidateCard(BaseModel):
    type: str
    items: list[dict[str, Any]] = []
    fields: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    reply_text: str
    candidates: list[CandidateCard] = []
    risk_level: RiskLevel = RiskLevel.NONE
