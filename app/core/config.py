from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"

load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Career Engine Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/career_engine"

    frontend_origin: str = "http://localhost:3000"
    public_site_base_url: str | None = None

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
    project_autofill_agent_workspace_dir: str = ".codexpert"
    project_autofill_agent_top_k: int = 5
    project_autofill_agent_max_iterations: int = 6
    project_similarity_embedding_model: str = "all-MiniLM-L6-v2"
    project_similarity_score_floor: float = 0.05
    project_similarity_score_ceiling: float = 0.95

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
