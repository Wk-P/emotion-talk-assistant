from pydantic import BaseModel, Field

from app.models.enums import Language


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
    # The picked persona (app/services/agent_config.py); None = default.
    persona: str | None = None


class HistoryMessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    # Assistant replies: the 0-5 rating given beside it, if any.
    rating: int | None = None


class SessionSyncResponse(BaseModel):
    # User/assistant messages after the first `after` ones, how many there
    # are in all, and whether the conversation was ended (maybe elsewhere).
    messages: list[HistoryMessageItem]
    total: int
    ended: bool


class ChatStreamRequest(BaseModel):
    session_id: str
    message: str | None = None
    # True for the "结束对话" button (no message): the closing reply, then
    # the conversation is locked.
    end: bool = False


class RatingRequest(BaseModel):
    rating: int | None = Field(default=None, ge=0, le=5)  # None clears it


class PersonaItem(BaseModel):
    id: str
    name: dict[str, str]
    intro: dict[str, str]


class PersonaList(BaseModel):
    personas: list[PersonaItem]
    default: str


class PersonaChoice(BaseModel):
    persona: str | None = None
