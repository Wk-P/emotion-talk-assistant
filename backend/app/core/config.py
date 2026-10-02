from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "emotion-talk-backend"
    environment: str = "development"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Fernet key for encrypting saved records at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    record_encryption_key: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    # Signs login access tokens (JWT). Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
