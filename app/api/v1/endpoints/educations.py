from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.education import (
    create_education,
    delete_education,
    get_education_by_id,
    list_educations_by_user_id,
    update_education,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.education import EducationCreateRequest, EducationResponse, EducationUpdateRequest

router = APIRouter(prefix="/educations", tags=["educations"])


def _to_education_response(item) -> EducationResponse:
    return EducationResponse(
        id=item.id,
        user_id=item.user_id,
        sort_order=item.sort_order,
        university=item.university,
        degree=item.degree,
        field=item.field,
        time_period=item.time_period,
        gpa=item.gpa,
        location=item.location,
        relevant_coursework=item.relevant_coursework,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[EducationResponse])
async def list_educations_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EducationResponse]:
    educations = await list_educations_by_user_id(db, current_user.id)
    return [_to_education_response(item) for item in educations]


@router.post("", response_model=EducationResponse, status_code=status.HTTP_201_CREATED)
async def create_education_endpoint(
    data: EducationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EducationResponse:
    payload = data.model_dump(mode="json")
    sort_order = payload.pop("sort_order", None)
    education = await create_education(db, current_user.id, payload, sort_order)
    return _to_education_response(education)


@router.patch("/{education_id}", response_model=EducationResponse)
async def update_education_endpoint(
    education_id: str,
    data: EducationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EducationResponse:
    education = await get_education_by_id(db, current_user.id, education_id)
    if not education:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Education not found")

    payload = data.model_dump(mode="json", exclude_unset=True)
    updated = await update_education(db, education, payload)
    return _to_education_response(updated)


@router.delete("/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education_endpoint(
    education_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    education = await get_education_by_id(db, current_user.id, education_id)
    if not education:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Education not found")
    await delete_education(db, education)