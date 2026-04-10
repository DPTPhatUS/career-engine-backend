import json
import uuid

from fastapi import HTTPException, status
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import decrypt_text, encrypt_text, get_fernet
from app.crud.auth import (
    create_oauth_state,
    delete_oauth_state,
    get_google_credential_by_user_id,
    get_oauth_state,
    upsert_google_credential,
)
from app.models.auth import User


def _build_flow(settings: Settings, state: str | None = None) -> Flow:
    flow = Flow.from_client_secrets_file(
        settings.google_client_secrets_file,
        scopes=settings.google_scopes,
        state=state,
    )
    flow.redirect_uri = settings.google_redirect_uri
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
