from typing import Any, Literal

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
    id: str
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
    # Ids of the stored messages for this turn, so the client can tell its
    # own turn apart from ones a sync brings in (no duplicates).
    user_message_id: str | None = None
    assistant_message_id: str | None = None


class SummaryCardContent(BaseModel):
    summary: str = ""
    plan: str = ""  # "" = no plan came up
    kindness: str = ""


class SummaryCardItem(BaseModel):
    """A conversation card (app/services/summary_card.py)."""

    id: str
    kind: Literal["review", "final"]
    content: SummaryCardContent
    # Shown after this many user/assistant messages.
    after_messages: int
    # Final card: None until the user picks, then "saved" | "discarded".
    decision: Literal["saved", "discarded"] | None = None


class CardDecisionRequest(BaseModel):
    save: bool
