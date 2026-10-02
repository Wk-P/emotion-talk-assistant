from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import Language, UserRole
from app.services.auth import MIN_PASSWORD_LENGTH, USERNAME_PATTERN


class AdminSessionItem(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    message_count: int
    record_count: int = 0


class AdminMessageItem(BaseModel):
    role: str
    content: str
    created_at: str
    # {prompt key: version} an assistant reply was generated with — see
    # app/models/prompt.py. None for user messages and older replies.
    prompt_versions: dict[str, int] | None = None
    # The OpenAI model that wrote an assistant reply (None for older ones).
    model: str | None = None


class AdminRecordItem(BaseModel):
    """A record the participant chose to save (with consent, see
    app/api/records.py), decrypted for research review."""

    id: str
    record_type: str
    payload: dict[str, Any]
    created_at: str


class AdminSessionExport(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    messages: list[AdminMessageItem]
    records: list[AdminRecordItem] = []


class AdminUserItem(BaseModel):
    id: str
    username: str
    role: UserRole
    is_active: bool
    created_at: str
    session_count: int


class SetActiveRequest(BaseModel):
    is_active: bool


class SetRoleRequest(BaseModel):
    role: UserRole


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    role: UserRole = UserRole.USER


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
