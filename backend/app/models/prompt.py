import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import Language


class PromptVersion(Base):
    """Admin-edited override of one editable prompt block (see
    app/prompts/registry.py for the set of keys and their code defaults).

    Append-only: every save is a new row with the next version number, and
    the highest version per (key, language) is the one in effect. Rollback
    and "reset to default" are just new rows carrying the older/default
    text, so the full edit trail is always kept. Version 0 is never stored —
    it means "the code default in app/prompts/", which is what's used while
    a (key, language) has no rows at all.

    Each assistant Message records the versions it was generated with (in
    Message.meta["prompt_versions"]) so research analysis can tell which
    conversation ran under which prompt text.
    """

    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("key", "language", "version", name="uq_prompt_key_lang_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[Language]
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptModule(Base):
    """Admin-managed settings for one block of the prompt shown in the admin
    "AI 对话设置" page (app/prompts/registry.py).

    Built-in blocks (the common principles and the four flows) only get a row
    once an admin renames or disables one — their key is the registry key.
    Admin-added blocks always have a row (key "custom.<id>") and can be
    deleted; their text lives in PromptVersion like any other block's, with
    an empty code default.

    group: "rules" (sent in every conversation, after the built-in
    principles), "flow" (sent only while `flow_key`'s flow is in use — flow
    routing itself stays in code, app/prompts/router.py) or "other" (sent in
    every conversation, after the flow).
    """

    __tablename__ = "prompt_modules"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    group: Mapped[str] = mapped_column(String(16))
    flow_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # {language: name}; only the languages an admin has named.
    names: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
