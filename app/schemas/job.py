from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class JobItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=1, max_length=8000)
    job_requirements: str = Field(min_length=1, max_length=8000)

    @field_validator("title", "job_description", "job_requirements")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field must not be empty.")
        return cleaned


class JobCreateRequest(JobItem):
    company_id: str
    sort_order: int | None = None

    @field_validator("company_id")
    @classmethod
    def _normalize_company_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("company_id must not be empty.")
        return cleaned


class JobUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    job_description: str | None = Field(default=None, min_length=1, max_length=8000)
    job_requirements: str | None = Field(default=None, min_length=1, max_length=8000)
    company_id: str | None = None
    sort_order: int | None = None

    @field_validator("title", "job_description", "job_requirements")
    @classmethod
    def _normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field must not be empty.")
        return cleaned

    @field_validator("company_id")
    @classmethod
    def _normalize_company_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("company_id must not be empty.")
        return cleaned

    @model_validator(mode="after")
    def _validate_company_id(self) -> "JobUpdateRequest":
        if "company_id" in self.model_fields_set and self.company_id is None:
            raise ValueError("company_id must not be null.")
        return self


class JobResponse(JobItem):
    id: str
    user_id: str
    company_id: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
