from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.session import ConversationSession
from app.models.user import User
from app.services.auth import decode_access_token


async def get_session_or_404(session_id: str, db: AsyncSession = Depends(get_db)) -> ConversationSession:
    result = await db.execute(select(ConversationSession).where(ConversationSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_access_token(token, get_settings().jwt_secret)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    # A disabled account's still-valid JWT (up to 30 days old, see
    # app/services/auth.py) must stop working immediately, not just at their
    # next login — treat it the same as no credential at all.
    if user is not None and not user.is_active:
        return None
    return user


async def get_current_user_required(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


async def get_current_admin_required(user: User = Depends(get_current_user_required)) -> User:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="admin access required")
    return user
