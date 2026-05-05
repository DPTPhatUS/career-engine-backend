from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.target_company import get_target_company_by_id
from app.crud.target_job import (
    create_target_job,
    delete_target_job,
    get_target_job_by_id,
    list_target_jobs_by_user_id,
    update_target_job,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.target_job import TargetJobCreateRequest, TargetJobResponse, TargetJobUpdateRequest

router = APIRouter(prefix="/target-jobs", tags=["target-jobs"])


def _to_target_job_response(item) -> TargetJobResponse:
    return TargetJobResponse(
        id=item.id,
        user_id=item.user_id,
        company_id=item.company_id,
        sort_order=item.sort_order,
        title=item.title,
        job_description=item.job_description,
        job_requirements=item.job_requirements,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[TargetJobResponse])
async def list_target_jobs_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TargetJobResponse]:
    jobs = await list_target_jobs_by_user_id(db, current_user.id)
    return [_to_target_job_response(item) for item in jobs]


@router.post("", response_model=TargetJobResponse, status_code=status.HTTP_201_CREATED)
async def create_target_job_endpoint(
    data: TargetJobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TargetJobResponse:
    company = await get_target_company_by_id(db, current_user.id, data.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found")

    payload = data.model_dump(mode="json")
    sort_order = payload.pop("sort_order", None)
    job = await create_target_job(db, current_user.id, payload, sort_order)
    return _to_target_job_response(job)


@router.patch("/{job_id}", response_model=TargetJobResponse)
async def update_target_job_endpoint(
    job_id: str,
    data: TargetJobUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TargetJobResponse:
    job = await get_target_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target job not found")

    payload = data.model_dump(mode="json", exclude_unset=True)
    company_id = payload.get("company_id")
    if company_id:
        company = await get_target_company_by_id(db, current_user.id, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found")

    updated = await update_target_job(db, job, payload)
    return _to_target_job_response(updated)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target_job_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    job = await get_target_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target job not found")
    await delete_target_job(db, job)
