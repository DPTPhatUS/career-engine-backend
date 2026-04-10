from app.core.config import Settings
from app.services.auth import hash_session_token, resolve_next_url


def test_hash_session_token_is_stable() -> None:
    token = "example-token"
    assert hash_session_token(token) == hash_session_token(token)
    assert hash_session_token(token) != hash_session_token("different-token")


def test_resolve_next_url_accepts_relative_and_same_origin() -> None:
    settings = Settings(frontend_origin="http://localhost:3000")

    assert resolve_next_url("/dashboard", settings) == "http://localhost:3000/dashboard"
    assert (
        resolve_next_url("http://localhost:3000/profile", settings)
        == "http://localhost:3000/profile"
    )


def test_resolve_next_url_rejects_other_origins() -> None:
    settings = Settings(frontend_origin="http://localhost:3000")
    assert resolve_next_url("https://evil.example.com/phish", settings) == "http://localhost:3000"
