from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume


async def create_resume(db: AsyncSession, user_id: str, title: str, payload: dict) -> Resume:
    resume = Resume(user_id=user_id, title=title, payload=payload)
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


async def get_resume_by_id(db: AsyncSession, user_id: str, resume_id: str) -> Resume | None:
    return await db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))


async def update_resume(db: AsyncSession, resume: Resume, title: str | None, payload: dict | None) -> Resume:
    if title is not None:
        resume.title = title
    if payload is not None:
        resume.payload = payload
    await db.commit()
    await db.refresh(resume)
    return resume


async def delete_resume(db: AsyncSession, resume: Resume) -> None:
    await db.delete(resume)
    await db.commit()
