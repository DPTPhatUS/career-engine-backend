from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import Job


async def list_jobs_by_user_id(db: AsyncSession, user_id: str) -> list[Job]:
    result = await db.scalars(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.sort_order.asc(), Job.created_at.asc())
    )
    return list(result)


async def get_job_by_id(db: AsyncSession, user_id: str, job_id: str) -> Job | None:
    return await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))


async def create_job(
    db: AsyncSession,
    user_id: str,
    data: dict,
    sort_order: int | None,
) -> Job:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(select(func.max(Job.sort_order)).where(Job.user_id == user_id))
        next_sort_order = 0 if max_sort is None else max_sort + 1

    job = Job(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_job(db: AsyncSession, job: Job, data: dict) -> Job:
    for field, value in data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


async def delete_job(db: AsyncSession, job: Job) -> None:
    await db.delete(job)
    await db.commit()
