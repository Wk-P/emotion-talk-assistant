from pydantic import BaseModel

from app.models.enums import Language, UserRole
from app.schemas.chat import HistoryMessageItem


class AdminSessionItem(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    message_count: int


class AdminSessionExport(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    messages: list[HistoryMessageItem]


class AdminUserItem(BaseModel):
    id: str
    email: str
    email_verified: bool
    role: UserRole
    is_active: bool
    created_at: str
    session_count: int


class SetActiveRequest(BaseModel):
    is_active: bool


class SetRoleRequest(BaseModel):
    role: UserRole
