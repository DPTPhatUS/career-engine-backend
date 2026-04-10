from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.crud.auth import get_or_create_user_by_email
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import OAuthCallbackResponse, OAuthStartResponse
from app.services.auth import create_google_oauth_start, handle_google_oauth_callback

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
) -> User:
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header",
        )

    return await get_or_create_user_by_email(db, x_user_email)


@router.get("/google/start", response_model=OAuthStartResponse)
async def google_start(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OAuthStartResponse:
    authorization_url, state = await create_google_oauth_start(db, current_user, settings)
    return OAuthStartResponse(authorization_url=authorization_url, state=state)


@router.get("/google/callback", response_model=OAuthCallbackResponse)
async def google_callback(
    state: str = Query(...),
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OAuthCallbackResponse:
    user = await handle_google_oauth_callback(db, state, code, settings)
    return OAuthCallbackResponse(user_id=user.id, email=user.email)
