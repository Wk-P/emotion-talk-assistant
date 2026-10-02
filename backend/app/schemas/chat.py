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


class HistoryMessageItem(BaseModel):
    role: str
    content: str
    created_at: str


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
