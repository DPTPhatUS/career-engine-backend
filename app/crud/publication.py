from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import PublicPortfolio


async def list_publications_by_user_id(db: AsyncSession, user_id: str) -> list[PublicPortfolio]:
    result = await db.scalars(
        select(PublicPortfolio).where(PublicPortfolio.user_id == user_id).order_by(PublicPortfolio.created_at.desc())
    )
    return list(result)


async def get_publication_by_id(db: AsyncSession, user_id: str, publication_id: str) -> PublicPortfolio | None:
    return await db.scalar(
        select(PublicPortfolio).where(PublicPortfolio.id == publication_id, PublicPortfolio.user_id == user_id)
    )


async def get_publication_by_slug(db: AsyncSession, slug: str) -> PublicPortfolio | None:
    return await db.scalar(select(PublicPortfolio).where(PublicPortfolio.slug == slug))


async def get_publication_by_source_resume_id(
    db: AsyncSession,
    source_resume_id: str,
    publication_id: str | None = None,
) -> PublicPortfolio | None:
    stmt = select(PublicPortfolio).where(PublicPortfolio.source_resume_id == source_resume_id)
    if publication_id is not None:
        stmt = stmt.where(PublicPortfolio.id != publication_id)
    return await db.scalar(stmt)


async def slug_exists_for_other_publication(
    db: AsyncSession, slug: str, publication_id: str | None = None
) -> bool:
    stmt = select(PublicPortfolio.id).where(PublicPortfolio.slug == slug)
    if publication_id is not None:
        stmt = stmt.where(PublicPortfolio.id != publication_id)
    return await db.scalar(stmt) is not None


async def create_publication(db: AsyncSession, user_id: str, data: dict) -> PublicPortfolio:
    publication = PublicPortfolio(user_id=user_id, **data)
    db.add(publication)
    await db.commit()
    await db.refresh(publication)
    return publication


async def update_publication(db: AsyncSession, publication: PublicPortfolio, data: dict) -> PublicPortfolio:
    for key, value in data.items():
        setattr(publication, key, value)
    await db.commit()
    await db.refresh(publication)
    return publication


async def delete_publication(db: AsyncSession, publication: PublicPortfolio) -> None:
    await db.delete(publication)
    await db.commit()
