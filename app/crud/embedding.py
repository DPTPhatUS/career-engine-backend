from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import JobEmbedding, ProjectEmbedding


async def get_project_embedding_by_project_id_and_model(
    db: AsyncSession,
    user_id: str,
    project_id: str,
    embedding_model: str,
) -> ProjectEmbedding | None:
    return await db.scalar(
        select(ProjectEmbedding).where(
            ProjectEmbedding.user_id == user_id,
            ProjectEmbedding.project_id == project_id,
            ProjectEmbedding.embedding_model == embedding_model,
        )
    )


async def upsert_project_embedding(
    db: AsyncSession,
    user_id: str,
    project_id: str,
    embedding_model: str,
    content_hash: str,
    embedding: list[float],
) -> ProjectEmbedding:
    existing = await get_project_embedding_by_project_id_and_model(
        db=db,
        user_id=user_id,
        project_id=project_id,
        embedding_model=embedding_model,
    )
    if existing:
        if existing.content_hash == content_hash:
            return existing
        existing.content_hash = content_hash
        existing.embedding = embedding
        await db.commit()
        await db.refresh(existing)
        return existing

    created = ProjectEmbedding(
        user_id=user_id,
        project_id=project_id,
        embedding_model=embedding_model,
        content_hash=content_hash,
        embedding=embedding,
    )
    db.add(created)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await get_project_embedding_by_project_id_and_model(
            db=db,
            user_id=user_id,
            project_id=project_id,
            embedding_model=embedding_model,
        )
        if existing is None:
            raise
        if existing.content_hash == content_hash:
            return existing
        existing.content_hash = content_hash
        existing.embedding = embedding
        await db.commit()
        await db.refresh(existing)
        return existing
    await db.refresh(created)
    return created


async def get_job_embedding_by_job_id_and_model(
    db: AsyncSession,
    user_id: str,
    job_id: str,
    embedding_model: str,
) -> JobEmbedding | None:
    return await db.scalar(
        select(JobEmbedding).where(
            JobEmbedding.user_id == user_id,
            JobEmbedding.job_id == job_id,
            JobEmbedding.embedding_model == embedding_model,
        )
    )


async def upsert_job_embedding(
    db: AsyncSession,
    user_id: str,
    job_id: str,
    embedding_model: str,
    content_hash: str,
    embedding: list[float],
) -> JobEmbedding:
    existing = await get_job_embedding_by_job_id_and_model(
        db=db,
        user_id=user_id,
        job_id=job_id,
        embedding_model=embedding_model,
    )
    if existing:
        if existing.content_hash == content_hash:
            return existing
        existing.content_hash = content_hash
        existing.embedding = embedding
        await db.commit()
        await db.refresh(existing)
        return existing

    created = JobEmbedding(
        user_id=user_id,
        job_id=job_id,
        embedding_model=embedding_model,
        content_hash=content_hash,
        embedding=embedding,
    )
    db.add(created)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await get_job_embedding_by_job_id_and_model(
            db=db,
            user_id=user_id,
            job_id=job_id,
            embedding_model=embedding_model,
        )
        if existing is None:
            raise
        if existing.content_hash == content_hash:
            return existing
        existing.content_hash = content_hash
        existing.embedding = embedding
        await db.commit()
        await db.refresh(existing)
        return existing
    await db.refresh(created)
    return created
