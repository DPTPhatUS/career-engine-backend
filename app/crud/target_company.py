from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import TargetCompany


async def list_target_companies_by_user_id(db: AsyncSession, user_id: str) -> list[TargetCompany]:
    result = await db.scalars(
        select(TargetCompany)
        .where(TargetCompany.user_id == user_id)
        .order_by(TargetCompany.sort_order.asc(), TargetCompany.created_at.asc())
    )
    return list(result)


async def get_target_company_by_id(
    db: AsyncSession,
    user_id: str,
    company_id: str,
) -> TargetCompany | None:
    return await db.scalar(
        select(TargetCompany).where(TargetCompany.id == company_id, TargetCompany.user_id == user_id)
    )


async def create_target_company(
    db: AsyncSession,
    user_id: str,
    data: dict,
    sort_order: int | None,
) -> TargetCompany:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(
            select(func.max(TargetCompany.sort_order)).where(TargetCompany.user_id == user_id)
        )
        next_sort_order = 0 if max_sort is None else max_sort + 1

    company = TargetCompany(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def update_target_company(
    db: AsyncSession,
    company: TargetCompany,
    data: dict,
) -> TargetCompany:
    for field, value in data.items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


async def delete_target_company(db: AsyncSession, company: TargetCompany) -> None:
    await db.delete(company)
    await db.commit()
