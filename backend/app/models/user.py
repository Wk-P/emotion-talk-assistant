import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # The login ID. Stored in the column still named "email" from when
    # accounts were email-based, so existing users keep logging in with
    # their email address as their ID and no data migration is needed.
    username: Mapped[str] = mapped_column("email", String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Unused since email verification was removed; kept only because the
    # existing column is NOT NULL.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[UserRole] = mapped_column(default=UserRole.USER)
    # Reversible alternative to deleting an account (see app/api/admin.py) —
    # login is refused while False, but nothing about the account is erased.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
