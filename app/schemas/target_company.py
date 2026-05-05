from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class TargetCompanyItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    company_url: HttpUrl | None = None
    overview: str | None = Field(default=None, max_length=8000)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name must not be empty.")
        return cleaned

    @field_validator("overview")
    @classmethod
    def _normalize_overview(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class TargetCompanyCreateRequest(TargetCompanyItem):
    sort_order: int | None = None


class TargetCompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company_url: HttpUrl | None = None
    overview: str | None = Field(default=None, max_length=8000)
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name must not be empty.")
        return cleaned

    @field_validator("overview")
    @classmethod
    def _normalize_overview(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _validate_name(self) -> "TargetCompanyUpdateRequest":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name must not be null.")
        return self


class TargetCompanyResponse(TargetCompanyItem):
    id: str
    user_id: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
