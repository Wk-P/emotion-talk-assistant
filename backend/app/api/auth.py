"""ID + password accounts. There is no email at all: no verification, and
no self-service password recovery — a user who forgets their password asks
an admin to set a new one (see app/api/admin.py reset_user_password)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_required
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import create_access_token, hash_password, normalize_username, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, get_settings().jwt_secret),
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Usable straight away — signs the new user in, nothing to confirm."""

    username = normalize_username(payload.username)
    if (await db.execute(select(User.id).where(User.username == username))).first() is not None:
        raise HTTPException(status_code=409, detail="username already taken")

    user = User(username=username, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == normalize_username(payload.username)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")
    return _token_response(user)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user_required)) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, role=user.role)
