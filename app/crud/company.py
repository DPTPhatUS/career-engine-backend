from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import Company


async def list_companies_by_user_id(db: AsyncSession, user_id: str) -> list[Company]:
    result = await db.scalars(
        select(Company)
        .where(Company.user_id == user_id)
        .order_by(Company.sort_order.asc(), Company.created_at.asc())
    )
    return list(result)


async def get_company_by_id(db: AsyncSession, user_id: str, company_id: str) -> Company | None:
    return await db.scalar(select(Company).where(Company.id == company_id, Company.user_id == user_id))


async def create_company(
    db: AsyncSession,
    user_id: str,
    data: dict,
    sort_order: int | None,
) -> Company:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(select(func.max(Company.sort_order)).where(Company.user_id == user_id))
        next_sort_order = 0 if max_sort is None else max_sort + 1

    company = Company(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def update_company(db: AsyncSession, company: Company, data: dict) -> Company:
    for field, value in data.items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


async def delete_company(db: AsyncSession, company: Company) -> None:
    await db.delete(company)
    await db.commit()
