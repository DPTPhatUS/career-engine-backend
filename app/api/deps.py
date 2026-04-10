from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.crud.auth import delete_session_by_token_hash, get_session_by_token_hash
from app.db.session import get_db
from app.models.auth import User
from app.services.auth import hash_session_token


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    session_token = request.cookies.get(settings.session_cookie_name)

    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = hash_session_token(session_token)
    user_session = await get_session_by_token_hash(db, token_hash)
    if not user_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    now = utcnow()
    if user_session.expires_at <= now:
        await delete_session_by_token_hash(db, token_hash)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = await db.get(User, user_session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session user")

    return user
