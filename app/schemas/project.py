from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

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


class ProjectAutofillRequest(BaseModel):
    github_url: HttpUrl


class ProjectAutofillResponse(ProjectItem):
    pass


class TailorProjectsRequest(BaseModel):
    job_title: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=1, max_length=8000)
    job_requirements: str = Field(min_length=1, max_length=8000)
    project_ids: list[str] = Field(min_length=1, max_length=5)

    @field_validator("job_title", "job_description", "job_requirements")
    @classmethod
    def _normalize_job_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field must not be empty.")
        return cleaned

    @model_validator(mode="after")
    def _normalize_project_ids(self) -> "TailorProjectsRequest":
        normalized_ids = [project_id.strip() for project_id in self.project_ids]
        if any(not project_id for project_id in normalized_ids):
            raise ValueError("project_ids cannot contain empty values.")
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("project_ids must not contain duplicates.")
        self.project_ids = normalized_ids
        return self


class TailoredProjectItem(ProjectItem):
    project_id: str


class TailoredProjectWarning(BaseModel):
    project_id: str | None = None
    reason_code: Literal["missing_github_url", "github_scan_failed", "generation_failed"]
    detail: str


class TailorProjectsResponse(BaseModel):
    tailored_projects: list[TailoredProjectItem] = Field(default_factory=list)
    skipped_projects: list[TailoredProjectWarning] = Field(default_factory=list)