from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.publication import get_publication_by_slug
from app.db.session import get_db
from app.schemas.publication import PublicPortfolioResponse

router = APIRouter(prefix="/public/portfolios", tags=["public-portfolios"])


@router.get("/{slug}", response_model=PublicPortfolioResponse)
async def get_public_portfolio_endpoint(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> PublicPortfolioResponse:
    publication = await get_publication_by_slug(db, slug)
    if not publication or not publication.is_published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public portfolio not found")
    return PublicPortfolioResponse(
        slug=publication.slug,
        title=publication.title,
        snapshot=publication.snapshot,
        published_at=publication.published_at,
        updated_at=publication.updated_at,
    )
