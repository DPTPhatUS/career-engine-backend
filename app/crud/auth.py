from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import GoogleCredential, OAuthLoginState, OAuthState, User, UserSession


async def get_or_create_user_by_email(db: AsyncSession, email: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user:
        return user

    user = User(email=email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_oauth_state(
    db: AsyncSession,
    state: str,
    user_id: str,
    code_verifier: str | None = None,
) -> OAuthState:
    row = OAuthState(state=state, user_id=user_id, code_verifier=code_verifier)
    db.add(row)
    await db.commit()
    return row


async def get_oauth_state(db: AsyncSession, state: str) -> OAuthState | None:
    return await db.scalar(select(OAuthState).where(OAuthState.state == state))


async def delete_oauth_state(db: AsyncSession, state_id: str) -> None:
    await db.execute(delete(OAuthState).where(OAuthState.id == state_id))


async def create_oauth_login_state(
    db: AsyncSession,
    state: str,
    next_url: str | None,
    code_verifier: str | None = None,
) -> OAuthLoginState:
    row = OAuthLoginState(state=state, next_url=next_url, code_verifier=code_verifier)
    db.add(row)
    await db.commit()
    return row


async def get_oauth_login_state(db: AsyncSession, state: str) -> OAuthLoginState | None:
    return await db.scalar(select(OAuthLoginState).where(OAuthLoginState.state == state))


async def delete_oauth_login_state(db: AsyncSession, state_id: str) -> None:
    await db.execute(delete(OAuthLoginState).where(OAuthLoginState.id == state_id))


async def get_google_credential_by_user_id(db: AsyncSession, user_id: str) -> GoogleCredential | None:
    return await db.scalar(select(GoogleCredential).where(GoogleCredential.user_id == user_id))


async def upsert_google_credential(
    db: AsyncSession,
    user_id: str,
    encrypted_credentials_json: str,
    scopes: str,
) -> None:
    existing = await get_google_credential_by_user_id(db, user_id)
    if existing:
        existing.encrypted_credentials_json = encrypted_credentials_json
        existing.scopes = scopes
    else:
        db.add(
            GoogleCredential(
                user_id=user_id,
                encrypted_credentials_json=encrypted_credentials_json,
                scopes=scopes,
            )
        )
    await db.commit()


async def create_user_session(
    db: AsyncSession,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
) -> UserSession:
    session = UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_token_hash(db: AsyncSession, token_hash: str) -> UserSession | None:
    return await db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


async def delete_session_by_token_hash(db: AsyncSession, token_hash: str) -> None:
    await db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
