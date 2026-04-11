from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import Profile


async def get_profile_by_user_id(db: AsyncSession, user_id: str) -> Profile | None:
    return await db.scalar(select(Profile).where(Profile.user_id == user_id))


async def upsert_profile(db: AsyncSession, user_id: str, data: dict) -> Profile:
    profile = await get_profile_by_user_id(db, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, **data)
        db.add(profile)
    else:
        for field, value in data.items():
            setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile