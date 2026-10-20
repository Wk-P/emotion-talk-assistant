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
    # The 0-5 ratings given beside AI replies: how many, and their average.
    rated_count: int = 0
    avg_rating: float | None = None


class AdminMessageItem(BaseModel):
    role: str
    content: str
    created_at: str
    # Assistant replies (None for user messages): the model and persona that
    # wrote it, and the 0-5 rating the user gave beside it.
    model: str | None = None
    persona: str | None = None
    rating: int | None = None


class AdminRecordItem(BaseModel):
    """A record the participant chose to save (with consent, see
    app/api/records.py), decrypted for research review."""

    id: str
    record_type: str
    payload: dict[str, Any]
    created_at: str


class AdminUserRecordItem(AdminRecordItem):
    """A record in the all-participants list (GET /api/admin/records)."""

    participant_label: str
    session_id: str
    # The participant deleted the conversation it came from; the record stays.
    session_deleted: bool


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
