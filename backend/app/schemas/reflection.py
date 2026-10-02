from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Language


class ReflectionAnswers(BaseModel):
    # The three questions of documents/02_内容与需求/每日省察功能.md, in order.
    helpful: str = Field(default="", max_length=4000)
    changed: str = Field(default="", max_length=4000)
    improve: str = Field(default="", max_length=4000)


class SaveReflectionRequest(BaseModel):
    language: Language
    answers: ReflectionAnswers


class ReflectionItem(BaseModel):
    id: str
    day: str
    language: Language
    answers: ReflectionAnswers
    created_at: datetime
    updated_at: datetime | None


class AdminReflectionItem(ReflectionItem):
    participant_label: str
