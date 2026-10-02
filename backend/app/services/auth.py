import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

_PBKDF2_ITERATIONS = 260_000
_JWT_ALGORITHM = "HS256"


# Shared by self sign-up (app/api/auth.py) and admin-created accounts
# (app/api/admin.py). IDs are case-insensitive: stored lowercased.
MIN_PASSWORD_LENGTH = 8
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


def normalize_username(username: str) -> str:
    return username.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iterations, salt, hex_digest = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), hex_digest)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: str, secret: str, expires_days: int = 30) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> str | None:
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
