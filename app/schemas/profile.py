from datetime import datetime

from app.schemas.resume import PersonalInfo


class ProfileUpsertRequest(PersonalInfo):
    pass


class ProfileResponse(PersonalInfo):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime