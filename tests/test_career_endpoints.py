from datetime import datetime, timezone
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.endpoints import educations as educations_endpoints
from app.api.v1.endpoints import profile as profile_endpoints
from app.api.v1.endpoints import projects as projects_endpoints
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    fake_user = SimpleNamespace(id="user-1", email="user@example.com")

    async def override_current_user() -> SimpleNamespace:
        return fake_user

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def test_get_profile_not_found(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_profile_by_user_id(db, user_id: str):
        return None

    monkeypatch.setattr(profile_endpoints, "get_profile_by_user_id", fake_get_profile_by_user_id)

    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json() == {"detail": "Profile not found"}


def test_put_profile_upsert_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_upsert_profile(db, user_id: str, data: dict):
        return SimpleNamespace(
            id="profile-1",
            user_id=user_id,
            created_at=_ts(),
            updated_at=_ts(),
            **data,
        )

    monkeypatch.setattr(profile_endpoints, "upsert_profile", fake_upsert_profile)

    response = client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+1 555 0100",
            "address": "City, ST",
            "github_label": "GitHub",
            "github_url": "https://github.com/ada",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "profile-1"
    assert body["user_id"] == "user-1"
    assert body["full_name"] == "Ada Lovelace"


def test_create_education_sends_payload_and_sort_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    async def fake_create_education(db, user_id: str, data: dict, sort_order: int | None):
        captured["data"] = data
        captured["sort_order"] = sort_order
        return SimpleNamespace(
            id="edu-1",
            user_id=user_id,
            sort_order=0,
            created_at=_ts(),
            updated_at=_ts(),
            **data,
        )

    monkeypatch.setattr(educations_endpoints, "create_education", fake_create_education)

    response = client.post(
        "/api/v1/educations",
        json={
            "university": "Example University",
            "degree": "B.S.",
            "field": "Computer Science",
            "time_period": "2020-2024",
            "gpa": "3.9",
            "location": "City, ST",
            "relevant_coursework": "Algorithms",
        },
    )

    assert response.status_code == 201
    assert captured["sort_order"] is None
    assert "sort_order" not in captured["data"]
    assert captured["data"]["university"] == "Example University"


def test_patch_education_not_found(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_education_by_id(db, user_id: str, education_id: str):
        return None

    monkeypatch.setattr(educations_endpoints, "get_education_by_id", fake_get_education_by_id)

    response = client.patch("/api/v1/educations/missing", json={"degree": "M.S."})
    assert response.status_code == 404
    assert response.json() == {"detail": "Education not found"}


def test_list_projects_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_projects_by_user_id(db, user_id: str):
        return [
            SimpleNamespace(
                id="project-1",
                user_id=user_id,
                sort_order=0,
                title="My Project",
                date_range="Jan 2024 - Mar 2024",
                github_url="https://github.com/org/repo",
                tech_stack="FastAPI, Postgres",
                bullets=["Did X", "Improved Y"],
                created_at=_ts(),
                updated_at=_ts(),
            )
        ]

    monkeypatch.setattr(projects_endpoints, "list_projects_by_user_id", fake_list_projects_by_user_id)

    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "project-1"


def test_delete_project_no_content(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(id="project-1", user_id="user-1")
    called = {"deleted": False}

    async def fake_get_project_by_id(db, user_id: str, project_id: str):
        return project

    async def fake_delete_project(db, project_arg):
        called["deleted"] = project_arg is project

    monkeypatch.setattr(projects_endpoints, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(projects_endpoints, "delete_project", fake_delete_project)

    response = client.delete("/api/v1/projects/project-1")
    assert response.status_code == 204
    assert called["deleted"] is True
