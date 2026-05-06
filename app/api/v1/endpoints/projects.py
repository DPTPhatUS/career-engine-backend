from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.crud.project import (
    create_project,
    delete_project,
    get_project_by_id,
    list_projects_by_user_id,
    update_project,
)
from app.crud.company import get_company_by_id
from app.crud.job import get_job_by_id
from app.db.session import get_db
from app.models.auth import User
from app.schemas.project import (
    ProjectAutofillRequest,
    ProjectAutofillResponse,
    ProjectCreateRequest,
    ProjectResponse,
    TailorProjectsRequest,
    TailorProjectsResponse,
    ProjectUpdateRequest,
)
from app.services.project_autofill import (
    GithubLoaderError,
    autofill_project_from_github,
    tailor_projects_for_job,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_project_response(item) -> ProjectResponse:
    return ProjectResponse(
        id=item.id,
        user_id=item.user_id,
        sort_order=item.sort_order,
        title=item.title,
        date_range=item.date_range,
        github_url=item.github_url,
        tech_stack=item.tech_stack,
        bullets=item.bullets,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("/autofill", response_model=ProjectAutofillResponse)
async def autofill_project_endpoint(
    data: ProjectAutofillRequest,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ProjectAutofillResponse:
    _ = current_user

    try:
        payload = await autofill_project_from_github(str(data.github_url), settings)
    except GithubLoaderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ProjectAutofillResponse(**payload)


@router.post("/tailor", response_model=TailorProjectsResponse)
async def tailor_projects_endpoint(
    data: TailorProjectsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TailorProjectsResponse:
    try:
        job_title = data.job_title
        job_description = data.job_description
        job_requirements = data.job_requirements
        company_name = None
        company_overview = None

        if data.job_id:
            job = await get_job_by_id(db, current_user.id, data.job_id)
            if not job:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

            company = await get_company_by_id(db, current_user.id, job.company_id)
            if not company:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

            job_title = job.title
            job_description = job.job_description
            job_requirements = job.job_requirements
            company_name = company.name
            company_overview = company.overview

        payload = await tailor_projects_for_job(
            db=db,
            user_id=current_user.id,
            project_ids=data.project_ids,
            job_title=job_title,
            job_description=job_description,
            job_requirements=job_requirements,
            company_name=company_name,
            company_overview=company_overview,
            settings=settings,
        )
    except GithubLoaderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return TailorProjectsResponse(**payload)


@router.get("", response_model=list[ProjectResponse])
async def list_projects_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    projects = await list_projects_by_user_id(db, current_user.id)
    return [_to_project_response(item) for item in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    data: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    payload = data.model_dump(mode="json")
    sort_order = payload.pop("sort_order", None)
    project = await create_project(db, current_user.id, payload, sort_order)
    return _to_project_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(
    project_id: str,
    data: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await get_project_by_id(db, current_user.id, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    payload = data.model_dump(mode="json", exclude_unset=True)
    updated = await update_project(db, project, payload)
    return _to_project_response(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await get_project_by_id(db, current_user.id, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await delete_project(db, project)