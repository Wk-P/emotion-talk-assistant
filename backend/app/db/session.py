from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    import app.models  # noqa: F401  (ensure models are registered on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_sessions_participated)
        await conn.run_sync(_add_sessions_flow_state)
        await conn.run_sync(_remap_retired_flow_keys)
        await conn.run_sync(_delete_unused_sessions)


def _add_sessions_participated(conn) -> None:
    """One-off in-place migration (no Alembic setup here): create_all never
    adds columns to an existing table. Backfill: anything with a user message
    counts as a real conversation. So does a session with no messages left
    that was ended or has saved records — its messages were purged at session
    end without DIALOGUE_HISTORY consent (see ConversationSession.participated).
    Everything else never had any user content."""

    from sqlalchemy import inspect, text

    columns = {c["name"] for c in inspect(conn).get_columns("sessions")}
    if "participated" in columns:
        return
    conn.execute(text("ALTER TABLE sessions ADD COLUMN participated BOOLEAN NOT NULL DEFAULT 0"))
    conn.execute(
        text(
            "UPDATE sessions SET participated = 1 WHERE "
            "id IN (SELECT session_id FROM messages WHERE role = 'USER') "
            "OR (id NOT IN (SELECT session_id FROM messages) "
            "AND (ended_at IS NOT NULL OR id IN (SELECT session_id FROM saved_records)))"
        )
    )


def _add_sessions_flow_state(conn) -> None:
    """One-off in-place migration: the stage column (app/services/flow.py).
    Existing sessions start empty and get a stage inferred on their next turn."""

    from sqlalchemy import inspect, text

    columns = {c["name"] for c in inspect(conn).get_columns("sessions")}
    if "flow_state" not in columns:
        conn.execute(text("ALTER TABLE sessions ADD COLUMN flow_state JSON NOT NULL DEFAULT '{}'"))


def _remap_retired_flow_keys(conn) -> None:
    """The four old flows became the flowchart stages (app/prompts/stages.py).
    Blocks admins had added under a retired flow move to the stage that
    replaced it. Runs on every startup; a no-op once done."""

    from sqlalchemy import text

    for old, new in (("flow.emotion_exploration", "flow.explore"), ("flow.recovery_plan", "flow.act")):
        conn.execute(text("UPDATE prompt_modules SET flow_key = :new WHERE flow_key = :old"), {"old": old, "new": new})


def _delete_unused_sessions(conn) -> None:
    """Sessions are only created on the user's first send (see
    app/api/session.py), so one still not `participated` after a few minutes
    is a failed first send or a pre-change leftover — no user content, safe
    to drop. Runs on every startup."""

    from sqlalchemy import text

    unused = "SELECT id FROM sessions WHERE participated = 0 AND created_at < datetime('now', '-10 minutes')"
    conn.execute(text(f"DELETE FROM messages WHERE session_id IN ({unused})"))
    conn.execute(text(f"DELETE FROM saved_records WHERE session_id IN ({unused})"))
    conn.execute(text(f"DELETE FROM sessions WHERE id IN ({unused})"))
