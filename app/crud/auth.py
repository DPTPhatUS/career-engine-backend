from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import GoogleCredential, OAuthState, User


async def get_or_create_user_by_email(db: AsyncSession, email: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user:
        return user

    user = User(email=email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_oauth_state(db: AsyncSession, state: str, user_id: str) -> OAuthState:
    row = OAuthState(state=state, user_id=user_id)
    db.add(row)
    await db.commit()
    return row


async def get_oauth_state(db: AsyncSession, state: str) -> OAuthState | None:
    return await db.scalar(select(OAuthState).where(OAuthState.state == state))


async def delete_oauth_state(db: AsyncSession, state_id: str) -> None:
    await db.execute(delete(OAuthState).where(OAuthState.id == state_id))


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
