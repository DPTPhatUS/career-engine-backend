from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.crud.auth import delete_session_by_token_hash
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import AuthMeResponse, LogoutResponse, OAuthCallbackResponse, OAuthStartResponse
from app.services.auth import (
    create_google_login_start,
    create_google_oauth_start,
    handle_google_login_callback,
    handle_google_oauth_callback,
    hash_session_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_secure(settings: Settings) -> bool:
    return settings.cookie_secure or settings.app_env.lower() != "development"


def _max_age(expires_at: datetime) -> int:
    remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(0, remaining)


@router.get("/google/login/start", response_model=OAuthStartResponse)
async def google_login_start(
    next_url: str | None = Query(default=None, alias="next"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OAuthStartResponse:
    authorization_url, state = await create_google_login_start(db, settings, next_url)
    return OAuthStartResponse(authorization_url=authorization_url, state=state)


@router.get("/google/login/callback")
async def google_login_callback(
    state: str = Query(...),
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    _user, raw_token, expires_at, redirect_to = await handle_google_login_callback(
        db,
        state,
        code,
        settings,
    )
    response = RedirectResponse(url=redirect_to, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=_max_age(expires_at),
        httponly=True,
        secure=_cookie_secure(settings),
        samesite=settings.cookie_samesite,
        path="/",
    )
    return response


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(current_user: User = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(user_id=current_user.id, email=current_user.email)


@router.post("/logout", response_model=LogoutResponse)
async def auth_logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LogoutResponse:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        await delete_session_by_token_hash(db, hash_session_token(raw_token))
        await db.commit()

    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return LogoutResponse(success=True)


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
