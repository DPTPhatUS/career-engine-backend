from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.profile import get_profile_by_user_id, upsert_profile
from app.db.session import get_db
from app.models.auth import User
from app.schemas.profile import ProfileResponse, ProfileUpsertRequest

router = APIRouter(prefix="/profile", tags=["profile"])


def _to_profile_response(item) -> ProfileResponse:
    return ProfileResponse(
        id=item.id,
        user_id=item.user_id,
        full_name=item.full_name,
        email=item.email,
        phone=item.phone,
        address=item.address,
        github_label=item.github_label,
        github_url=item.github_url,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=ProfileResponse)
async def get_profile_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    profile = await get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return _to_profile_response(profile)


@router.put("", response_model=ProfileResponse)
async def upsert_profile_endpoint(
    data: ProfileUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    profile = await upsert_profile(db, current_user.id, data.model_dump(mode="json"))
    return _to_profile_response(profile)