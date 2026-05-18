from collections.abc import Generator
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.schemas.publication import PortfolioContactOptions, PortfolioSelection
from app.services.publication import (
    SlugConflictError,
    build_public_portfolio_snapshot,
    update_portfolio_publication,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    fake_user = SimpleNamespace(id="user-1", email="user@example.com")

    async def override_current_user() -> SimpleNamespace:
        return fake_user

    async def override_get_db():
        class FakeDb:
            async def rollback(self):
                pass

        yield FakeDb()

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _resume_payload() -> dict:
    return {
        "personal_info": {
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+1 555 0100",
            "address": "City, ST",
            "github_label": "GitHub",
            "github_url": "https://github.com/ada",
        },
        "education": [{"university": "Example U", "degree": "BS", "field": "CS", "time_period": "2020-2024"}],
        "projects": [
            {"title": "Project A", "date_range": "2025", "bullets": ["A1"]},
            {"title": "Project B", "date_range": "2026", "bullets": ["B1"]},
        ],
        "skills": [{"label": "Languages", "values": "Python"}],
    }


def _contact(
    email: bool = False, phone: bool = False, address: bool = False, github: bool = True
) -> PortfolioContactOptions:
    return PortfolioContactOptions(
        include_email=email,
        include_phone=phone,
        include_address=address,
        include_github=github,
    )


def _selection(
    education_indexes: list[int] | None = None,
    project_indexes: list[int] | None = None,
    skill_indexes: list[int] | None = None,
) -> PortfolioSelection:
    return PortfolioSelection(
        education_indexes=education_indexes,
        project_indexes=project_indexes,
        skill_indexes=skill_indexes,
    )


def test_publish_defaults_redact_email_phone_address() -> None:
    resume = SimpleNamespace(id="resume-1", payload=_resume_payload())
    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(),
        selection=_selection(),
        title="Portfolio",
    )
    personal = snapshot.personal_info
    assert personal.full_name == "Ada Lovelace"
    assert personal.email is None
    assert personal.phone is None
    assert personal.address is None
    assert personal.github_url == "https://github.com/ada"


def test_publish_includes_opted_in_email_only() -> None:
    resume = SimpleNamespace(id="resume-1", payload=_resume_payload())
    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(email=True, phone=False, address=False, github=False),
        selection=_selection(),
        title="Portfolio",
    )
    personal = snapshot.personal_info
    assert personal.email == "ada@example.com"
    assert personal.phone is None
    assert personal.address is None
    assert personal.github_url is None


def test_selected_indexes_reduce_public_snapshot_sections() -> None:
    resume = SimpleNamespace(id="resume-1", payload=_resume_payload())
    resume.payload["education"].append(
        {"university": "Second U", "degree": "MS", "field": "AI", "time_period": "2024-2026"}
    )
    resume.payload["skills"].append({"label": "Tools", "values": "PostgreSQL"})
    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(),
        selection=_selection(education_indexes=[1], project_indexes=[1], skill_indexes=[1]),
        title="Portfolio",
    )
    assert len(snapshot.education) == 1
    assert snapshot.education[0].university == "Second U"
    assert len(snapshot.projects) == 1
    assert snapshot.projects[0].title == "Project B"
    assert len(snapshot.skills) == 1
    assert snapshot.skills[0].label == "Tools"


def test_empty_selection_arrays_publish_empty_sections() -> None:
    resume = SimpleNamespace(id="resume-1", payload=_resume_payload())
    snapshot = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(),
        selection=_selection(education_indexes=[], project_indexes=[], skill_indexes=[]),
        title="Portfolio",
    )
    assert snapshot.education == []
    assert snapshot.projects == []
    assert snapshot.skills == []


def test_slug_collision_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1.endpoints import portfolio_publications as endpoint

    async def fake_create_portfolio_publication(*args, **kwargs):
        raise SlugConflictError()

    monkeypatch.setattr(endpoint, "create_portfolio_publication", fake_create_portfolio_publication)

    response = client.post(
        "/api/v1/portfolio-publications",
        json={
            "source_resume_id": "resume-1",
            "slug": "ada",
            "title": "Ada Portfolio",
            "contact": _contact().model_dump(),
            "selection": _selection().model_dump(),
        },
    )
    assert response.status_code == 409


def test_integrity_error_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1.endpoints import portfolio_publications as endpoint

    async def fake_create_portfolio_publication(*args, **kwargs):
        raise IntegrityError("insert", {}, Exception("unique violation"))

    monkeypatch.setattr(endpoint, "create_portfolio_publication", fake_create_portfolio_publication)

    response = client.post(
        "/api/v1/portfolio-publications",
        json={
            "source_resume_id": "resume-1",
            "slug": "ada",
            "title": "Ada Portfolio",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Publication conflict"}


def test_public_endpoint_returns_404_for_unpublished(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1.endpoints import public_portfolios as endpoint

    async def fake_get_publication_by_slug(db, slug: str):
        return SimpleNamespace(
            id="pub-1",
            slug=slug,
            title="Ada Portfolio",
            snapshot={"title": "Ada Portfolio"},
            is_published=False,
            published_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(endpoint, "get_publication_by_slug", fake_get_publication_by_slug)
    response = client.get("/api/v1/public/portfolios/ada")
    assert response.status_code == 404


def test_republishing_refreshes_snapshot_but_prior_snapshot_frozen() -> None:
    payload = _resume_payload()
    resume = SimpleNamespace(id="resume-1", payload=payload)
    first = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(),
        selection=_selection(),
        title="Portfolio",
    )

    payload["projects"][0]["title"] = "Changed Project A"
    frozen = deepcopy(first.model_dump(mode="json"))
    assert frozen["projects"][0]["title"] == "Project A"

    republished = build_public_portfolio_snapshot(
        resume=resume,
        contact=_contact(),
        selection=_selection(),
        title="Portfolio",
    )
    assert republished.projects[0].title == "Changed Project A"


def test_update_without_selection_preserves_existing_snapshot_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.services import publication as publication_service
    from app.schemas.publication import PortfolioPublicationUpdateRequest

    publication = SimpleNamespace(
        id="pub-1",
        source_resume_id="resume-1",
        slug="ada",
        title="Portfolio",
        snapshot={
            "education": [_resume_payload()["education"][0]],
            "projects": [_resume_payload()["projects"][1]],
            "skills": [_resume_payload()["skills"][0]],
        },
        is_published=False,
        published_at=datetime.now(timezone.utc),
    )
    resume = SimpleNamespace(id="resume-1", title="Resume", payload=_resume_payload())
    captured: dict = {}

    async def fake_get_resume_by_id(db, user_id: str, resume_id: str):
        return resume

    async def fake_slug_exists_for_other_publication(db, slug: str, publication_id: str | None = None):
        return False

    async def fake_get_publication_by_source_resume_id(db, source_resume_id: str, publication_id: str | None = None):
        return None

    async def fake_update_publication(db, publication, data: dict):
        captured["data"] = data
        return SimpleNamespace(**{**publication.__dict__, **data})

    monkeypatch.setattr(publication_service, "get_resume_by_id", fake_get_resume_by_id)
    monkeypatch.setattr(
        publication_service,
        "slug_exists_for_other_publication",
        fake_slug_exists_for_other_publication,
    )
    monkeypatch.setattr(
        publication_service,
        "get_publication_by_source_resume_id",
        fake_get_publication_by_source_resume_id,
    )
    monkeypatch.setattr(publication_service, "update_publication", fake_update_publication)

    asyncio.run(
        update_portfolio_publication(
            object(),
            "user-1",
            publication,
            PortfolioPublicationUpdateRequest(title="Updated Portfolio"),
        )
    )

    snapshot = captured["data"]["snapshot"]
    assert [project["title"] for project in snapshot["projects"]] == ["Project B"]
    assert captured["data"]["is_published"] is False
