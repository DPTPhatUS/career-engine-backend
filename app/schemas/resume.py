from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class PersonalInfo(BaseModel):
    full_name: str
    email: str
    phone: str
    address: str
    github_label: str | None = "GitHub"
    github_url: HttpUrl | None = None


class EducationItem(BaseModel):
    university: str
    degree: str
    field: str
    time_period: str
    gpa: str | None = None
    location: str | None = None
    relevant_coursework: str | None = None


class ProjectItem(BaseModel):
    title: str
    date_range: str
    github_url: HttpUrl | None = None
    tech_stack: str | None = None
    bullets: list[str] = Field(default_factory=list)


class SkillCategory(BaseModel):
    label: str
    values: str


class ResumePayload(BaseModel):
    personal_info: PersonalInfo
    target_job_id: str | None = None
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)


class ResumeCreateRequest(BaseModel):
    title: str
    payload: ResumePayload


class ResumeUpdateRequest(BaseModel):
    title: str | None = None
    payload: ResumePayload | None = None


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    title: str
    payload: ResumePayload
    created_at: datetime
    updated_at: datetime


class GenerateDocRequest(BaseModel):
    document_title: str | None = None


class GenerateDocResponse(BaseModel):
    document_id: str
    document_url: str
