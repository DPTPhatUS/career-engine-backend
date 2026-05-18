from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.crud.publication import (
    delete_publication,
    get_publication_by_id,
    list_publications_by_user_id,
    update_publication,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.publication import (
    PortfolioPublicationCreateRequest,
    PortfolioPublicationOwnerResponse,
    PortfolioPublicationUpdateRequest,
    PortfolioPublicationVisibilityRequest,
)
from app.services.publication import (
    InvalidPublicationError,
    PublicationNotFoundError,
    SlugConflictError,
    build_public_url,
    create_portfolio_publication,
    update_portfolio_publication,
)

router = APIRouter(prefix="/portfolio-publications", tags=["portfolio-publications"])


def _to_owner_response(item, settings: Settings) -> PortfolioPublicationOwnerResponse:
    return PortfolioPublicationOwnerResponse(
        id=item.id,
        user_id=item.user_id,
        source_resume_id=item.source_resume_id,
        slug=item.slug,
        public_url=build_public_url(settings, item.slug),
        title=item.title,
        snapshot=item.snapshot,
        is_published=item.is_published,
        published_at=item.published_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[PortfolioPublicationOwnerResponse])
async def list_portfolio_publications_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[PortfolioPublicationOwnerResponse]:
    rows = await list_publications_by_user_id(db, current_user.id)
    return [_to_owner_response(item, settings) for item in rows]


@router.post("", response_model=PortfolioPublicationOwnerResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio_publication_endpoint(
    data: PortfolioPublicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PortfolioPublicationOwnerResponse:
    try:
        publication = await create_portfolio_publication(db, current_user.id, data)
    except PublicationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidPublicationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Publication conflict") from exc
    return _to_owner_response(publication, settings)


@router.put("/{publication_id}", response_model=PortfolioPublicationOwnerResponse)
async def update_portfolio_publication_endpoint(
    publication_id: str,
    data: PortfolioPublicationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PortfolioPublicationOwnerResponse:
    publication = await get_publication_by_id(db, current_user.id, publication_id)
    if not publication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    try:
        updated = await update_portfolio_publication(db, current_user.id, publication, data)
    except PublicationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidPublicationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Publication conflict") from exc
    return _to_owner_response(updated, settings)


@router.patch("/{publication_id}/visibility", response_model=PortfolioPublicationOwnerResponse)
async def set_portfolio_publication_visibility_endpoint(
    publication_id: str,
    data: PortfolioPublicationVisibilityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PortfolioPublicationOwnerResponse:
    publication = await get_publication_by_id(db, current_user.id, publication_id)
    if not publication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    payload: dict = {"is_published": data.is_published}
    if data.is_published and not publication.published_at:
        from datetime import datetime, timezone

        payload["published_at"] = datetime.now(timezone.utc)
    updated = await update_publication(db, publication, payload)
    return _to_owner_response(updated, settings)


@router.delete("/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio_publication_endpoint(
    publication_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    publication = await get_publication_by_id(db, current_user.id, publication_id)
    if not publication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    await delete_publication(db, publication)
