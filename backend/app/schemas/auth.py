from pydantic import BaseModel, Field

from app.models.enums import UserRole
from app.services.auth import MIN_PASSWORD_LENGTH, USERNAME_PATTERN


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class LoginRequest(BaseModel):
    # No pattern here: accounts from the email era log in with their email.
    username: str = Field(min_length=1, max_length=255)
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse
