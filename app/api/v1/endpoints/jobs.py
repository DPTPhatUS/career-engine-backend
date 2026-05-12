from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.company import get_company_by_id
from app.crud.job import create_job, delete_job, get_job_by_id, list_jobs_by_user_id, update_job
from app.db.session import get_db
from app.models.auth import User
from app.schemas.job import JobCreateRequest, JobResponse, JobUpdateRequest

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_job_response(item) -> JobResponse:
    return JobResponse(
        id=item.id,
        user_id=item.user_id,
        company_id=item.company_id,
        sort_order=item.sort_order,
        title=item.title,
        job_description=item.job_description,
        job_requirements=item.job_requirements,
        stage=item.stage,
        deadline=item.deadline,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[JobResponse])
async def list_jobs_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    jobs = await list_jobs_by_user_id(db, current_user.id)
    return [_to_job_response(item) for item in jobs]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    data: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    company = await get_company_by_id(db, current_user.id, data.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    payload = data.model_dump()
    sort_order = payload.pop("sort_order", None)
    job = await create_job(db, current_user.id, payload, sort_order)
    return _to_job_response(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job_endpoint(
    job_id: str,
    data: JobUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await get_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    payload = data.model_dump(exclude_unset=True)
    company_id = payload.get("company_id")
    if company_id:
        company = await get_company_by_id(db, current_user.id, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    updated = await update_job(db, job, payload)
    return _to_job_response(updated)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    job = await get_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    await delete_job(db, job)
