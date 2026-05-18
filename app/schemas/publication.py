from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.resume import EducationItem, ProjectItem, SkillCategory


class PortfolioContactOptions(BaseModel):
    include_email: bool = False
    include_phone: bool = False
    include_address: bool = False
    include_github: bool = True


class PortfolioSelection(BaseModel):
    education_indexes: list[int] | None = None
    project_indexes: list[int] | None = None
    skill_indexes: list[int] | None = None


class PublicPortfolioSnapshotPersonalInfo(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    github_label: str | None = None
    github_url: str | None = None


class PublicPortfolioSnapshot(BaseModel):
    title: str | None = None
    personal_info: PublicPortfolioSnapshotPersonalInfo
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)


class PortfolioPublicationCreateRequest(BaseModel):
    source_resume_id: str
    slug: str
    title: str | None = None
    contact: PortfolioContactOptions = Field(default_factory=PortfolioContactOptions)
    selection: PortfolioSelection = Field(default_factory=PortfolioSelection)
    is_published: bool = True


class PortfolioPublicationUpdateRequest(BaseModel):
    source_resume_id: str | None = None
    slug: str | None = None
    title: str | None = None
    contact: PortfolioContactOptions = Field(default_factory=PortfolioContactOptions)
    selection: PortfolioSelection = Field(default_factory=PortfolioSelection)
    is_published: bool | None = None


class PortfolioPublicationVisibilityRequest(BaseModel):
    is_published: bool


class PortfolioPublicationOwnerResponse(BaseModel):
    id: str
    user_id: str
    source_resume_id: str | None
    slug: str
    public_url: str
    title: str
    snapshot: PublicPortfolioSnapshot
    is_published: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicPortfolioResponse(BaseModel):
    slug: str
    title: str
    snapshot: PublicPortfolioSnapshot
    published_at: datetime | None
    updated_at: datetime
