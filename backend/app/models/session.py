import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import Language


class ConversationSession(Base):
    """A single participant's one-time session (PRD: used once per user).

    `confirmed_context` holds only information the user has confirmed or edited —
    never raw AI guesses (design principle: AI-proposed emotions/situations are
    candidates only, per turn, until the user confirms them).
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Client-generated identifier (browser localStorage, no login) that groups
    # sessions belonging to the same device so a history list is possible
    # without a full account system. Null for older sessions created before
    # this existed.
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Set when the session was started while logged in — takes priority over
    # device_id for history grouping (see app/api/session.py).
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    language: Mapped[Language] = mapped_column(default=Language.ZH)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set on the first user message (typed or a picked option). Starting a
    # chat saves the session and the code-sent opening message right away, so
    # sessions still False were opened but never used — hidden from every
    # list/count/export and cleaned up on the owner's next start (see
    # app/api/session.py). A flag rather than "has a user message" because
    # messages get purged at session end without DIALOGUE_HISTORY consent,
    # and such a session was still a real conversation.
    participated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Rolling self-criticism signal in [0, 1], used to prioritize acceptance support
    # over exploration/action planning (design principle 4, 9.3).
    self_criticism_level: Mapped[float] = mapped_column(Float, default=0.0)

    # {"situation": str|None, "emotions": [str], "needs": [str], "beliefs": [str],
    #  "acculturation_domains": [str], "values": [str], "goals": [...],
    #  "seb_entries": [...], "last_intent": str|None}
    confirmed_context: Mapped[dict] = mapped_column(JSON, default=dict)

    # Per-category booleans, see ConsentCategory. Defaults are all False (opt-in only).
    consent: Mapped[dict] = mapped_column(JSON, default=dict)
