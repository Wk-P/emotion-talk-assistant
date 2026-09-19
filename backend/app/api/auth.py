from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user_required
from app.core.config import get_settings
from app.db.session import get_db
from app.models.auth_token import AuthToken
from app.models.enums import AuthTokenPurpose
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth import create_access_token, generate_token, hash_password, verify_password
from app.services.email import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

_MIN_PASSWORD_LENGTH = 8


def _expiry(hours: int) -> datetime:
    # naive UTC: SQLite round-trips DateTime(timezone=True) values as naive,
    # so comparisons below must use the same naive-UTC convention.
    return datetime.utcnow() + timedelta(hours=hours)


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    email = payload.email.lower()
    if len(payload.password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"password must be at least {_MIN_PASSWORD_LENGTH} characters")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="email already registered")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.flush()

    token = generate_token()
    db.add(AuthToken(user_id=user.id, token=token, purpose=AuthTokenPurpose.VERIFY_EMAIL, expires_at=_expiry(24)))
    await db.commit()

    settings = get_settings()
    link = f"{settings.frontend_base_url}/verify-email?token={token}"
    await run_in_threadpool(
        send_email,
        user.email,
        "Emotion-AI - 验证你的邮箱 / Verify your email",
        f"<p><strong>Emotion-AI</strong></p><p>点击链接验证邮箱(24小时内有效):</p><p><a href='{link}'>{link}</a></p>",
    )
    return MessageResponse(message="registered, check your email to verify")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    result = await db.execute(select(AuthToken).where(AuthToken.token == payload.token))
    token_row = result.scalar_one_or_none()
    if (
        token_row is None
        or token_row.purpose != AuthTokenPurpose.VERIFY_EMAIL
        or token_row.used_at is not None
        or token_row.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="invalid or expired token")

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    user.email_verified = True
    token_row.used_at = datetime.utcnow()
    db.add_all([user, token_row])
    await db.commit()
    return MessageResponse(message="email verified")


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="email not verified")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")

    token = create_access_token(user.id, get_settings().jwt_secret)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, email=user.email, email_verified=True, role=user.role),
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Always return the same message regardless of whether the email exists,
    # so this endpoint can't be used to check who is registered.
    if user is not None:
        token = generate_token()
        db.add(
            AuthToken(user_id=user.id, token=token, purpose=AuthTokenPurpose.RESET_PASSWORD, expires_at=_expiry(1))
        )
        await db.commit()

        settings = get_settings()
        link = f"{settings.frontend_base_url}/reset-password?token={token}"
        await run_in_threadpool(
            send_email,
            user.email,
            "Emotion-AI - 重置密码 / Reset your password",
            f"<p><strong>Emotion-AI</strong></p><p>点击链接重置密码(1小时内有效):</p><p><a href='{link}'>{link}</a></p>",
        )

    return MessageResponse(message="if that email exists, a reset link was sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    if len(payload.new_password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"password must be at least {_MIN_PASSWORD_LENGTH} characters")

    result = await db.execute(select(AuthToken).where(AuthToken.token == payload.token))
    token_row = result.scalar_one_or_none()
    if (
        token_row is None
        or token_row.purpose != AuthTokenPurpose.RESET_PASSWORD
        or token_row.used_at is not None
        or token_row.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="invalid or expired token")

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = datetime.utcnow()
    db.add_all([user, token_row])
    await db.commit()
    return MessageResponse(message="password reset")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user_required)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, email_verified=user.email_verified, role=user.role)
