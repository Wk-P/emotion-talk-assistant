import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import MessageRole


class Message(Base):
    """Working conversation history for the active session.

    Ephemeral by default: purged on session end unless the user has granted
    ConsentCategory.DIALOGUE_HISTORY (PRD: 会话临时使用信息 vs 长期保存记录 must be
    kept distinct and each requires an explicit, revocable choice).
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole]
    content: Mapped[str] = mapped_column(Text)
    # candidate cards, detected intent, risk flags, etc. attached to this turn
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
