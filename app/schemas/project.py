from datetime import datetime

from pydantic import HttpUrl

from app.schemas.resume import ProjectItem


class ProjectCreateRequest(ProjectItem):
    sort_order: int | None = None


class ProjectUpdateRequest(ProjectItem):
    title: str | None = None
    date_range: str | None = None
    github_url: HttpUrl | None = None
    tech_stack: str | None = None
    bullets: list[str] | None = None
    sort_order: int | None = None


class ProjectResponse(ProjectItem):
    id: str
    user_id: str
    sort_order: int
    created_at: datetime
    updated_at: datetime