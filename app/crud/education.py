from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import Education


async def list_educations_by_user_id(db: AsyncSession, user_id: str) -> list[Education]:
    result = await db.scalars(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.sort_order.asc(), Education.created_at.asc())
    )
    return list(result)


async def get_education_by_id(db: AsyncSession, user_id: str, education_id: str) -> Education | None:
    return await db.scalar(
        select(Education).where(Education.id == education_id, Education.user_id == user_id)
    )


async def create_education(db: AsyncSession, user_id: str, data: dict, sort_order: int | None) -> Education:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(select(func.max(Education.sort_order)).where(Education.user_id == user_id))
        next_sort_order = 0 if max_sort is None else max_sort + 1

    education = Education(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(education)
    await db.commit()
    await db.refresh(education)
    return education


async def update_education(db: AsyncSession, education: Education, data: dict) -> Education:
    for field, value in data.items():
        setattr(education, field, value)

    await db.commit()
    await db.refresh(education)
    return education


async def delete_education(db: AsyncSession, education: Education) -> None:
    await db.delete(education)
    await db.commit()