from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Career Engine Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/career_engine"

    frontend_origin: str = "http://localhost:3000"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_login_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/login/callback"
    google_scopes: list[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]
    )

    session_cookie_name: str = "ce_session"
    session_ttl_seconds: int = 3600
    session_renewal_window_seconds: int = 900
    cookie_samesite: str = "lax"
    cookie_secure: bool = False

    encryption_key: str = "replace-me-with-a-fernet-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
