import json
from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().record_encryption_key
    if not key:
        raise RuntimeError(
            "RECORD_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and put it in backend/.env"
        )
    return Fernet(key.encode())


def encrypt_json(payload: dict) -> bytes:
    return _fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def decrypt_json(token: bytes | str) -> dict:
    if isinstance(token, str):
        token = token.encode("utf-8")
    return json.loads(_fernet().decrypt(token).decode("utf-8"))
