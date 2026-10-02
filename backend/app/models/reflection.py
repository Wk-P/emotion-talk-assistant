import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import Language


class DailyReflection(Base):
    """The daily usage reflection questionnaire (documents/每日省察功能.md;
    flowchart step "성찰일지 및 사용경험 작성"). One per owner per day —
    re-submitting the same day updates it.

    Owned by the logged-in account (there is no anonymous use; device_id is
    a leftover from when there was). Answers are Fernet-encrypted JSON
    (app/services/crypto.py), as with saved records.
    """

    __tablename__ = "daily_reflections"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_reflection_user_day"),
        UniqueConstraint("device_id", "day", name="uq_reflection_device_day"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # The writer's local calendar date (YYYY-MM-DD), so "today" means their today.
    day: Mapped[str] = mapped_column(String(10), index=True)
    language: Mapped[Language] = mapped_column(default=Language.ZH)
    answers_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
