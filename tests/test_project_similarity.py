import asyncio
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import project_similarity


def _ts(offset_seconds: int = 0) -> datetime:
    return datetime.fromtimestamp(1_700_000_000 + offset_seconds, tz=timezone.utc)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        project_similarity_embedding_model="all-MiniLM-L6-v2",
        project_similarity_score_floor=0.35,
        project_similarity_score_ceiling=0.85,
    )


class _FakeModel:
    def __init__(self, embedding_by_marker: dict[str, list[float]], calls: list[str]) -> None:
        self._embedding_by_marker = embedding_by_marker
        self._calls = calls

    def encode(self, text: str) -> list[float]:
        self._calls.append(text)
        for marker, embedding in self._embedding_by_marker.items():
            if marker in text:
                return embedding
        raise AssertionError(f"No fake embedding configured for text: {text}")


def test_rank_projects_orders_by_cosine_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(
        id="job-1",
        title="Backend Engineer",
        job_description="Build APIs",
        job_requirements="FastAPI and SQL",
    )
    projects = [
        SimpleNamespace(
            id="project-1",
            title="API Platform",
            tech_stack="FastAPI",
            bullets=["Built APIs"],
            github_url="https://github.com/org/repo",
            sort_order=3,
            created_at=_ts(2),
        ),
        SimpleNamespace(
            id="project-2",
            title="Data Warehouse",
            tech_stack="dbt",
            bullets=["Built ETL"],
            github_url="https://github.com/org/repo2",
            sort_order=1,
            created_at=_ts(1),
        ),
        SimpleNamespace(
            id="project-3",
            title="Platform Services",
            tech_stack="Python",
            bullets=["Shipped service layer"],
            github_url=None,
            sort_order=0,
            created_at=_ts(0),
        ),
    ]

    calls: list[str] = []
    fake_model = _FakeModel(
        {
            "Backend Engineer": [1.0, 0.0],
            "API Platform": [0.95, 0.05],
            "Data Warehouse": [0.0, 1.0],
            "Platform Services": [0.4, 0.6],
        },
        calls,
    )
    monkeypatch.setattr(project_similarity, "_get_sentence_transformer", lambda _model_name: fake_model)
    monkeypatch.setattr(project_similarity, "get_job_embedding_by_job_id_and_model", _async_return(None))
    monkeypatch.setattr(project_similarity, "get_project_embedding_by_project_id_and_model", _async_return(None))
    monkeypatch.setattr(project_similarity, "upsert_job_embedding", _async_noop())
    monkeypatch.setattr(project_similarity, "upsert_project_embedding", _async_noop())

    ranked = asyncio.run(
        project_similarity.rank_projects_for_job(
            db=object(),
            user_id="user-1",
            job=job,
            projects=projects,
            settings=_settings(),
        )
    )

    assert [item["project_id"] for item in ranked] == ["project-1", "project-3", "project-2"]


def test_rank_projects_reuses_cached_project_embedding_when_hash_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = SimpleNamespace(
        id="job-1",
        title="Backend Engineer",
        job_description="Build APIs",
        job_requirements="FastAPI and SQL",
    )
    project = SimpleNamespace(
        id="project-1",
        title="API Platform",
        tech_stack="FastAPI",
        bullets=["Built APIs"],
        github_url="https://github.com/org/repo",
        sort_order=0,
        created_at=_ts(0),
    )

    project_text = project_similarity._build_project_text(project)
    matching_hash = hashlib.sha256(project_text.encode("utf-8")).hexdigest()
    cached_project_embedding = SimpleNamespace(content_hash=matching_hash, embedding=[0.9, 0.1])

    calls: list[str] = []
    fake_model = _FakeModel({"Backend Engineer": [1.0, 0.0]}, calls)
    monkeypatch.setattr(project_similarity, "_get_sentence_transformer", lambda _model_name: fake_model)
    monkeypatch.setattr(project_similarity, "get_job_embedding_by_job_id_and_model", _async_return(None))
    monkeypatch.setattr(
        project_similarity,
        "get_project_embedding_by_project_id_and_model",
        _async_return(cached_project_embedding),
    )
    monkeypatch.setattr(project_similarity, "upsert_job_embedding", _async_noop())

    upsert_project_called = {"called": False}

    async def fake_upsert_project_embedding(*args, **kwargs):
        upsert_project_called["called"] = True
        _ = (args, kwargs)

    monkeypatch.setattr(project_similarity, "upsert_project_embedding", fake_upsert_project_embedding)

    asyncio.run(
        project_similarity.rank_projects_for_job(
            db=object(),
            user_id="user-1",
            job=job,
            projects=[project],
            settings=_settings(),
        )
    )

    assert len(calls) == 1
    assert "Backend Engineer" in calls[0]
    assert upsert_project_called["called"] is False


def test_rank_projects_recomputes_project_embedding_when_content_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = SimpleNamespace(
        id="job-1",
        title="Backend Engineer",
        job_description="Build APIs",
        job_requirements="FastAPI and SQL",
    )
    project = SimpleNamespace(
        id="project-1",
        title="API Platform v2",
        tech_stack="FastAPI",
        bullets=["Built APIs"],
        github_url=None,
        sort_order=0,
        created_at=_ts(0),
    )

    calls: list[str] = []
    fake_model = _FakeModel(
        {
            "Backend Engineer": [1.0, 0.0],
            "API Platform v2": [0.8, 0.2],
        },
        calls,
    )
    monkeypatch.setattr(project_similarity, "_get_sentence_transformer", lambda _model_name: fake_model)
    monkeypatch.setattr(project_similarity, "get_job_embedding_by_job_id_and_model", _async_return(None))
    monkeypatch.setattr(
        project_similarity,
        "get_project_embedding_by_project_id_and_model",
        _async_return(SimpleNamespace(content_hash="stale-hash", embedding=[0.1, 0.9])),
    )
    monkeypatch.setattr(project_similarity, "upsert_job_embedding", _async_noop())

    captured: dict = {}

    async def fake_upsert_project_embedding(*, db, user_id, project_id, embedding_model, content_hash, embedding):
        captured["project_id"] = project_id
        captured["content_hash"] = content_hash
        captured["embedding"] = embedding
        _ = (db, user_id, embedding_model)

    monkeypatch.setattr(project_similarity, "upsert_project_embedding", fake_upsert_project_embedding)

    asyncio.run(
        project_similarity.rank_projects_for_job(
            db=object(),
            user_id="user-1",
            job=job,
            projects=[project],
            settings=_settings(),
        )
    )

    assert len(calls) == 2
    assert captured["project_id"] == "project-1"
    assert captured["embedding"] == [0.8, 0.2]


def test_rank_projects_clamps_display_scores_and_keeps_projects_without_github(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = SimpleNamespace(
        id="job-1",
        title="Backend Engineer",
        job_description="Build APIs",
        job_requirements="FastAPI and SQL",
    )
    projects = [
        SimpleNamespace(
            id="project-low",
            title="Opposite Direction",
            tech_stack="N/A",
            bullets=[],
            github_url=None,
            sort_order=1,
            created_at=_ts(1),
        ),
        SimpleNamespace(
            id="project-high",
            title="Same Direction",
            tech_stack="N/A",
            bullets=[],
            github_url=None,
            sort_order=0,
            created_at=_ts(0),
        ),
    ]

    calls: list[str] = []
    fake_model = _FakeModel(
        {
            "Backend Engineer": [1.0, 0.0],
            "Opposite Direction": [-1.0, 0.0],
            "Same Direction": [1.0, 0.0],
        },
        calls,
    )
    monkeypatch.setattr(project_similarity, "_get_sentence_transformer", lambda _model_name: fake_model)
    monkeypatch.setattr(project_similarity, "get_job_embedding_by_job_id_and_model", _async_return(None))
    monkeypatch.setattr(project_similarity, "get_project_embedding_by_project_id_and_model", _async_return(None))
    monkeypatch.setattr(project_similarity, "upsert_job_embedding", _async_noop())
    monkeypatch.setattr(project_similarity, "upsert_project_embedding", _async_noop())

    ranked = asyncio.run(
        project_similarity.rank_projects_for_job(
            db=object(),
            user_id="user-1",
            job=job,
            projects=projects,
            settings=_settings(),
        )
    )

    scores = {item["project_id"]: item["similarity_score"] for item in ranked}
    assert scores["project-high"] == 100
    assert scores["project-low"] == 0
    assert set(scores.keys()) == {"project-high", "project-low"}


def _async_return(value):
    async def _inner(*args, **kwargs):
        _ = (args, kwargs)
        return value

    return _inner


def _async_noop():
    async def _inner(*args, **kwargs):
        _ = (args, kwargs)
        return None

    return _inner
