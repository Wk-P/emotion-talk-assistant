import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SummaryCard(Base):
    """A conversation card the program gave the user (app/services/summary_card.py):
    "review" when they came back after a long break, "final" after they ended
    the conversation. Only a final card can be saved to "我的记录" — that copy
    is a SavedRecord; this row is what was shown.

    `content` is {"summary", "plan", "kindness"}; emptied when the user
    chose not to keep a final card.
    """

    __tablename__ = "summary_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # "review" | "final"
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    # How many user/assistant messages came before it — where it shows in
    # the chat, and where counting rounds for the next review card starts.
    after_messages: Mapped[int] = mapped_column(Integer, default=0)
    # Final card only: None until the user picks, then "saved" | "discarded".
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
