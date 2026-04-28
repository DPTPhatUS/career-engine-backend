from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.crud.resume import (
    create_resume as create_resume_row,
    delete_resume as delete_resume_row,
    get_resume_by_id,
    list_resumes_by_user_id,
    update_resume as update_resume_row,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.resume import (
    GenerateDocRequest,
    GenerateDocResponse,
    ResumeCreateRequest,
    ResumeResponse,
    ResumeUpdateRequest,
)
from app.services.resume_generation import generate_document_for_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _to_resume_response(item) -> ResumeResponse:
    return ResumeResponse(
        id=item.id,
        user_id=item.user_id,
        title=item.title,
        payload=item.payload,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[ResumeResponse])
async def list_resumes_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeResponse]:
    resumes = await list_resumes_by_user_id(db, current_user.id)
    return [_to_resume_response(item) for item in resumes]


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_resume_endpoint(
    data: ResumeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    resume = await create_resume_row(
        db,
        current_user.id,
        data.title,
        data.payload.model_dump(mode="json"),
    )
    return _to_resume_response(resume)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume_endpoint(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    resume = await get_resume_by_id(db, current_user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return _to_resume_response(resume)


@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume_endpoint(
    resume_id: str,
    data: ResumeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    resume = await get_resume_by_id(db, current_user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    updated = await update_resume_row(
        db,
        resume,
        data.title,
        data.payload.model_dump(mode="json") if data.payload else None,
    )
    return _to_resume_response(updated)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume_endpoint(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    resume = await get_resume_by_id(db, current_user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    await delete_resume_row(db, resume)


@router.post("/{resume_id}/generate-doc", response_model=GenerateDocResponse)
async def generate_doc_endpoint(
    resume_id: str,
    data: GenerateDocRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GenerateDocResponse:
    resume = await get_resume_by_id(db, current_user.id, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return await generate_document_for_resume(db, current_user, resume, settings, data)
