from pydantic import BaseModel

from app.models.enums import Language


class AdminSessionItem(BaseModel):
    session_id: str
    participant_label: str
    language: Language
    created_at: str
    ended_at: str | None
    message_count: int
