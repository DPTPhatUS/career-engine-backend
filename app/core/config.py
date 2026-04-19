from functools import lru_cache
from typing import Literal

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

    github_api_base_url: str = "https://api.github.com"
    github_token: str = ""

    project_autofill_llm_provider: Literal["mistral", "openai", "gemini"] = "mistral"
    project_autofill_mistral_model: str = "mistral-small-latest"
    project_autofill_openai_model: str = "gpt-5-nano"
    project_autofill_gemini_model: str = "gemini-2.5-flash"
    project_autofill_llm_temperature: float = 0.2
    project_autofill_llm_timeout_seconds: int = 45
    project_autofill_http_timeout_seconds: int = 20
    project_autofill_max_files: int = 60
    project_autofill_max_chars: int = 120000

    mistral_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    session_cookie_name: str = "ce_session"
    session_ttl_seconds: int = 3600
    session_renewal_window_seconds: int = 900
    cookie_samesite: str = "lax"
    cookie_secure: bool = False

    encryption_key: str = "replace-me-with-a-fernet-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
