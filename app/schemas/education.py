from datetime import datetime

from app.schemas.resume import EducationItem


class EducationCreateRequest(EducationItem):
    sort_order: int | None = None


class EducationUpdateRequest(EducationItem):
    university: str | None = None
    degree: str | None = None
    field: str | None = None
    time_period: str | None = None
    sort_order: int | None = None


class EducationResponse(EducationItem):
    id: str
    user_id: str
    sort_order: int
    created_at: datetime
    updated_at: datetime