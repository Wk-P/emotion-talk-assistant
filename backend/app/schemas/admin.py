from pydantic import BaseModel

from app.models.enums import Language, UserRole


class AdminSessionItem(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    message_count: int


class AdminMessageItem(BaseModel):
    role: str
    content: str
    created_at: str
    # {prompt key: version} an assistant reply was generated with — see
    # app/models/prompt.py. None for user messages and older replies.
    prompt_versions: dict[str, int] | None = None


class AdminSessionExport(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    messages: list[AdminMessageItem]


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
