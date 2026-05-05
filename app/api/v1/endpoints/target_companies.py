from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.target_company import (
    create_target_company,
    delete_target_company,
    get_target_company_by_id,
    list_target_companies_by_user_id,
    update_target_company,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.target_company import (
    TargetCompanyCreateRequest,
    TargetCompanyResponse,
    TargetCompanyUpdateRequest,
)

router = APIRouter(prefix="/target-companies", tags=["target-companies"])


def _to_target_company_response(item) -> TargetCompanyResponse:
    return TargetCompanyResponse(
        id=item.id,
        user_id=item.user_id,
        sort_order=item.sort_order,
        name=item.name,
        company_url=item.company_url,
        overview=item.overview,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[TargetCompanyResponse])
async def list_target_companies_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TargetCompanyResponse]:
    companies = await list_target_companies_by_user_id(db, current_user.id)
    return [_to_target_company_response(item) for item in companies]


@router.post("", response_model=TargetCompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_target_company_endpoint(
    data: TargetCompanyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TargetCompanyResponse:
    payload = data.model_dump(mode="json")
    sort_order = payload.pop("sort_order", None)
    company = await create_target_company(db, current_user.id, payload, sort_order)
    return _to_target_company_response(company)


@router.patch("/{company_id}", response_model=TargetCompanyResponse)
async def update_target_company_endpoint(
    company_id: str,
    data: TargetCompanyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TargetCompanyResponse:
    company = await get_target_company_by_id(db, current_user.id, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found")

    payload = data.model_dump(mode="json", exclude_unset=True)
    updated = await update_target_company(db, company, payload)
    return _to_target_company_response(updated)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target_company_endpoint(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    company = await get_target_company_by_id(db, current_user.id, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found")
    await delete_target_company(db, company)
