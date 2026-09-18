import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import RecordType


class SavedRecord(Base):
    """A record the user explicitly chose to save for reuse or weekly review
    (design principles 7.4, 8.5, 8.6, 11). Never written implicitly.

    `payload_encrypted` stores a Fernet-encrypted JSON blob (see
    app/services/crypto.py) so that a DB dump alone does not disclose content.
    Deleting a row here must also purge any copy used by the personalization
    service (see app/services/personalization.py).
    """

    __tablename__ = "saved_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    record_type: Mapped[RecordType]
    payload_encrypted: Mapped[bytes] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Reflects the consent state at save time; a later consent revocation for the
    # matching category triggers deletion, not just a flag flip.
    consented_category: Mapped[str] = mapped_column(String(64))
