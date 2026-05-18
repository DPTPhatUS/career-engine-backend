import re
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.publication import (
    create_publication,
    get_publication_by_source_resume_id,
    slug_exists_for_other_publication,
    update_publication,
)
from app.crud.resume import get_resume_by_id
from app.models.publication import PublicPortfolio
from app.models.resume import Resume
from app.schemas.publication import (
    PortfolioContactOptions,
    PortfolioSelection,
    PortfolioPublicationCreateRequest,
    PortfolioPublicationUpdateRequest,
    PublicPortfolioSnapshot,
    PublicPortfolioSnapshotPersonalInfo,
)
from app.schemas.resume import ResumePayload


class PublicationError(Exception):
    pass


class SlugConflictError(PublicationError):
    pass


class InvalidPublicationError(PublicationError):
    pass


class PublicationNotFoundError(PublicationError):
    pass


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise InvalidPublicationError("Invalid slug")
    return slug


def validate_selection_indexes(selection: PortfolioSelection, resume_payload: ResumePayload) -> None:
    education_count = len(resume_payload.education)
    for idx in selection.education_indexes or []:
        if idx < 0 or idx >= education_count:
            raise InvalidPublicationError("Invalid education selection indexes")

    project_count = len(resume_payload.projects)
    for idx in selection.project_indexes or []:
        if idx < 0 or idx >= project_count:
            raise InvalidPublicationError("Invalid project selection indexes")

    skill_count = len(resume_payload.skills)
    for idx in selection.skill_indexes or []:
        if idx < 0 or idx >= skill_count:
            raise InvalidPublicationError("Invalid skill selection indexes")


def build_public_portfolio_snapshot(
    *, resume: Resume, contact: PortfolioContactOptions, selection: PortfolioSelection, title: str | None
) -> PublicPortfolioSnapshot:
    payload = ResumePayload.model_validate(resume.payload)
    validate_selection_indexes(selection, payload)

    selected_education = (
        [payload.education[idx] for idx in selection.education_indexes]
        if selection.education_indexes is not None
        else payload.education
    )
    selected_projects = (
        [payload.projects[idx] for idx in selection.project_indexes]
        if selection.project_indexes is not None
        else payload.projects
    )
    selected_skills = (
        [payload.skills[idx] for idx in selection.skill_indexes]
        if selection.skill_indexes is not None
        else payload.skills
    )
    personal = payload.personal_info
    return PublicPortfolioSnapshot(
        title=title,
        personal_info=PublicPortfolioSnapshotPersonalInfo(
            full_name=personal.full_name,
            email=personal.email if contact.include_email else None,
            phone=personal.phone if contact.include_phone else None,
            address=personal.address if contact.include_address else None,
            github_label=personal.github_label if contact.include_github else None,
            github_url=str(personal.github_url) if contact.include_github and personal.github_url else None,
        ),
        education=selected_education,
        projects=selected_projects,
        skills=selected_skills,
    )


def build_public_url(settings: Settings, slug: str) -> str:
    base = settings.public_site_base_url or settings.frontend_origin
    return f"{base.rstrip('/')}/u/{slug}"


def _snapshot_item_indexes(source_items: list, snapshot_items: list | None) -> list[int]:
    if snapshot_items is None:
        return []

    used_indexes: set[int] = set()
    indexes: list[int] = []

    for snapshot_item in snapshot_items:
        for index, source_item in enumerate(source_items):
            if index in used_indexes:
                continue

            source_payload = source_item.model_dump(mode="json", exclude_none=True)
            if source_payload == snapshot_item:
                used_indexes.add(index)
                indexes.append(index)
                break

    return indexes


def _selection_from_snapshot(publication: PublicPortfolio, payload: ResumePayload) -> PortfolioSelection:
    snapshot = publication.snapshot or {}
    return PortfolioSelection(
        education_indexes=_snapshot_item_indexes(payload.education, snapshot.get("education")),
        project_indexes=_snapshot_item_indexes(payload.projects, snapshot.get("projects")),
        skill_indexes=_snapshot_item_indexes(payload.skills, snapshot.get("skills")),
    )


def _merge_update_selection(
    requested: PortfolioSelection,
    existing: PortfolioSelection,
) -> PortfolioSelection:
    return PortfolioSelection(
        education_indexes=(
            requested.education_indexes
            if requested.education_indexes is not None
            else existing.education_indexes
        ),
        project_indexes=(
            requested.project_indexes
            if requested.project_indexes is not None
            else existing.project_indexes
        ),
        skill_indexes=(
            requested.skill_indexes
            if requested.skill_indexes is not None
            else existing.skill_indexes
        ),
    )


async def create_portfolio_publication(
    db: AsyncSession, user_id: str, data: PortfolioPublicationCreateRequest
) -> PublicPortfolio:
    resume = await get_resume_by_id(db, user_id, data.source_resume_id)
    if not resume:
        raise PublicationNotFoundError("Resume not found")

    slug = normalize_slug(data.slug)
    if await slug_exists_for_other_publication(db, slug):
        raise SlugConflictError("Slug already exists")
    if await get_publication_by_source_resume_id(db, resume.id):
        raise SlugConflictError("Resume already has a public portfolio")

    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=data.contact,
        selection=data.selection,
        title=data.title or resume.title,
    )
    now = datetime.now(timezone.utc) if data.is_published else None
    return await create_publication(
        db,
        user_id=user_id,
        data={
            "source_resume_id": resume.id,
            "slug": slug,
            "title": data.title or resume.title,
            "snapshot": deepcopy(snapshot.model_dump(mode="json")),
            "is_published": data.is_published,
            "published_at": now,
        },
    )


async def update_portfolio_publication(
    db: AsyncSession,
    user_id: str,
    publication: PublicPortfolio,
    data: PortfolioPublicationUpdateRequest,
) -> PublicPortfolio:
    source_resume_id = data.source_resume_id or publication.source_resume_id
    if not source_resume_id:
        raise PublicationNotFoundError("Resume not found")

    resume = await get_resume_by_id(db, user_id, source_resume_id)
    if not resume:
        raise PublicationNotFoundError("Resume not found")

    slug = normalize_slug(data.slug or publication.slug)
    if await slug_exists_for_other_publication(db, slug, publication.id):
        raise SlugConflictError("Slug already exists")
    if await get_publication_by_source_resume_id(db, resume.id, publication.id):
        raise SlugConflictError("Resume already has a public portfolio")

    title = data.title or publication.title or resume.title
    resume_payload = ResumePayload.model_validate(resume.payload)
    selection = _merge_update_selection(
        data.selection,
        _selection_from_snapshot(publication, resume_payload),
    )
    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=data.contact,
        selection=selection,
        title=title,
    )
    is_published = publication.is_published if data.is_published is None else data.is_published
    published_at = publication.published_at
    if is_published and not published_at:
        published_at = datetime.now(timezone.utc)
    return await update_publication(
        db,
        publication=publication,
        data={
            "source_resume_id": source_resume_id,
            "slug": slug,
            "title": title,
            "snapshot": deepcopy(snapshot.model_dump(mode="json")),
            "is_published": is_published,
            "published_at": published_at,
        },
    )
