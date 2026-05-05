from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import TargetJob


async def list_target_jobs_by_user_id(db: AsyncSession, user_id: str) -> list[TargetJob]:
    result = await db.scalars(
        select(TargetJob)
        .where(TargetJob.user_id == user_id)
        .order_by(TargetJob.sort_order.asc(), TargetJob.created_at.asc())
    )
    return list(result)


async def get_target_job_by_id(db: AsyncSession, user_id: str, job_id: str) -> TargetJob | None:
    return await db.scalar(select(TargetJob).where(TargetJob.id == job_id, TargetJob.user_id == user_id))


async def create_target_job(
    db: AsyncSession,
    user_id: str,
    data: dict,
    sort_order: int | None,
) -> TargetJob:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(select(func.max(TargetJob.sort_order)).where(TargetJob.user_id == user_id))
        next_sort_order = 0 if max_sort is None else max_sort + 1

    job = TargetJob(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_target_job(db: AsyncSession, job: TargetJob, data: dict) -> TargetJob:
    for field, value in data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


async def delete_target_job(db: AsyncSession, job: TargetJob) -> None:
    await db.delete(job)
    await db.commit()
