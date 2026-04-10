import json
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlparse
import uuid

from fastapi import HTTPException, status
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import decrypt_text, encrypt_text, get_fernet
from app.crud.auth import (
    create_oauth_login_state,
    create_oauth_state,
    create_user_session,
    delete_oauth_login_state,
    delete_oauth_state,
    get_or_create_user_by_email,
    get_oauth_login_state,
    get_google_credential_by_user_id,
    get_oauth_state,
    upsert_google_credential,
)
from app.models.auth import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_session_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def make_session_expiry(settings: Settings) -> datetime:
    return utcnow() + timedelta(seconds=settings.session_ttl_seconds)


def resolve_next_url(next_url: str | None, settings: Settings) -> str:
    if not next_url:
        return settings.frontend_origin

    if next_url.startswith("/"):
        return f"{settings.frontend_origin.rstrip('/')}{next_url}"

    frontend = urlparse(settings.frontend_origin)
    target = urlparse(next_url)
    if target.scheme == frontend.scheme and target.netloc == frontend.netloc:
        return next_url

    return settings.frontend_origin


def _build_flow(settings: Settings, state: str | None = None, redirect_uri: str | None = None) -> Flow:
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            ),
        )

    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                settings.google_redirect_uri,
                settings.google_login_redirect_uri,
            ],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.google_scopes,
        state=state,
    )

    flow.redirect_uri = redirect_uri or settings.google_redirect_uri
    return flow


async def create_google_oauth_start(
    db: AsyncSession,
    user: User,
    settings: Settings,
) -> tuple[str, str]:
    state = str(uuid.uuid4())
    await create_oauth_state(db, state, user.id)

    flow = _build_flow(settings, state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url, state


async def create_google_login_start(
    db: AsyncSession,
    settings: Settings,
    next_url: str | None,
) -> tuple[str, str]:
    state = str(uuid.uuid4())
    await create_oauth_login_state(db, state, resolve_next_url(next_url, settings))

    flow = _build_flow(settings, state=state, redirect_uri=settings.google_login_redirect_uri)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url, state


async def handle_google_oauth_callback(
    db: AsyncSession,
    state: str,
    code: str,
    settings: Settings,
) -> User:
    oauth_state = await get_oauth_state(db, state)
    if not oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    user = await db.get(User, oauth_state.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    flow = _build_flow(settings, state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials

    fernet = get_fernet(settings)
    encrypted_credentials = encrypt_text(creds.to_json(), fernet)
    scopes = " ".join(creds.scopes or settings.google_scopes)

    await upsert_google_credential(db, user.id, encrypted_credentials, scopes)
    await delete_oauth_state(db, oauth_state.id)
    await db.commit()
    return user


async def handle_google_login_callback(
    db: AsyncSession,
    state: str,
    code: str,
    settings: Settings,
) -> tuple[User, str, datetime, str]:
    oauth_state = await get_oauth_login_state(db, state)
    if not oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    flow = _build_flow(settings, state=state, redirect_uri=settings.google_login_redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server OAuth is not configured (missing GOOGLE_CLIENT_ID)",
        )

    if not creds.id_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing id_token in OAuth response")

    try:
        token_info = id_token.verify_oauth2_token(
            creds.id_token,
            Request(),
            audience=settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google id_token") from exc
    email = token_info.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email not available")

    if token_info.get("email_verified") is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email is not verified")

    user = await get_or_create_user_by_email(db, email)

    fernet = get_fernet(settings)
    encrypted_credentials = encrypt_text(creds.to_json(), fernet)
    scopes = " ".join(creds.scopes or settings.google_scopes)
    await upsert_google_credential(db, user.id, encrypted_credentials, scopes)

    raw_token = secrets.token_urlsafe(48)
    expires_at = make_session_expiry(settings)
    await create_user_session(db, user.id, hash_session_token(raw_token), expires_at)

    await delete_oauth_login_state(db, oauth_state.id)
    await db.commit()

    redirect_to = oauth_state.next_url or settings.frontend_origin
    return user, raw_token, expires_at, redirect_to


def should_renew_session(expires_at: datetime, settings: Settings) -> bool:
    remaining = (expires_at - utcnow()).total_seconds()
    return remaining <= settings.session_renewal_window_seconds


def renew_session_expiry(settings: Settings) -> datetime:
    return make_session_expiry(settings)


async def get_google_credentials_for_user(
    db: AsyncSession,
    user: User,
    settings: Settings,
) -> Credentials:
    row = await get_google_credential_by_user_id(db, user.id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account not connected for this user",
        )

    fernet = get_fernet(settings)
    raw_json = decrypt_text(row.encrypted_credentials_json, fernet)
    info = json.loads(raw_json)

    creds = Credentials.from_authorized_user_info(info=info, scopes=settings.google_scopes)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            row.encrypted_credentials_json = encrypt_text(creds.to_json(), fernet)
            await db.commit()
        except RefreshError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token refresh failed. Reconnect Google account.",
            ) from exc

    if not creds.valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credentials are invalid. Reconnect Google account.",
        )

    return creds
