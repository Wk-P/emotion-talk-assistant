from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CrisisResource(Base):
    """Verified support-resource directory (design principle 8.4/10).

    The AI must never invent contact details — it may only surface rows from
    this table. Seed/update this table from verified sources (school
    counseling centers, national hotlines); `verified_at` is shown to the user
    alongside the contact so staleness is visible. `name`/`description` are
    JSON {"zh": str, "ko": str} so the resource card matches the session language.
    """

    __tablename__ = "crisis_resources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    country: Mapped[str] = mapped_column(String(8))  # "KR" | "CN"
    category: Mapped[str] = mapped_column(String(64))  # e.g. "school_counseling", "national_hotline"
    name: Mapped[dict] = mapped_column(JSON)
    description: Mapped[dict] = mapped_column(JSON)
    contact: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
