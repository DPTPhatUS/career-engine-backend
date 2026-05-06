from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.company import (
    create_company,
    delete_company,
    get_company_by_id,
    list_companies_by_user_id,
    update_company,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.company import CompanyCreateRequest, CompanyResponse, CompanyUpdateRequest

router = APIRouter(prefix="/companies", tags=["companies"])


def _to_company_response(item) -> CompanyResponse:
    return CompanyResponse(
        id=item.id,
        user_id=item.user_id,
        sort_order=item.sort_order,
        name=item.name,
        company_url=item.company_url,
        overview=item.overview,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[CompanyResponse])
async def list_companies_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyResponse]:
    companies = await list_companies_by_user_id(db, current_user.id)
    return [_to_company_response(item) for item in companies]


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
    data: CompanyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    payload = data.model_dump(mode="json")
    sort_order = payload.pop("sort_order", None)
    company = await create_company(db, current_user.id, payload, sort_order)
    return _to_company_response(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company_endpoint(
    company_id: str,
    data: CompanyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    company = await get_company_by_id(db, current_user.id, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    payload = data.model_dump(mode="json", exclude_unset=True)
    updated = await update_company(db, company, payload)
    return _to_company_response(updated)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_endpoint(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    company = await get_company_by_id(db, current_user.id, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    await delete_company(db, company)
