from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.auth import User
from app.models.resume import GeneratedDocument, Resume
from app.schemas.resume import GenerateDocRequest, GenerateDocResponse, ResumePayload
from app.services.auth import get_google_credentials_for_user
from app.services.google_docs import GoogleDocsService
from app.services.resume_writer import build_resume_requests


async def generate_document_for_resume(
    db: AsyncSession,
    user: User,
    resume: Resume,
    settings: Settings,
    request_data: GenerateDocRequest,
) -> GenerateDocResponse:
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    creds = await get_google_credentials_for_user(db, user, settings)
    docs = GoogleDocsService(creds)

    title = request_data.document_title or resume.title
    document_id = docs.create_document(title=title)

    start_index = docs.get_append_index(document_id)
    payload_model = ResumePayload.model_validate(resume.payload)
    requests, _ = build_resume_requests(payload=payload_model, start_index=start_index)
    docs.batch_update(document_id=document_id, requests=requests)

    doc_url = f"https://docs.google.com/document/d/{document_id}/edit"
    db.add(
        GeneratedDocument(
            resume_id=resume.id,
            user_id=user.id,
            document_id=document_id,
            document_url=doc_url,
        )
    )
    await db.commit()

    return GenerateDocResponse(document_id=document_id, document_url=doc_url)
