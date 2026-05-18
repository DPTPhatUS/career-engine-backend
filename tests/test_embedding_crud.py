import asyncio

from sqlalchemy.exc import IntegrityError

from app.crud.embedding import upsert_job_embedding, upsert_project_embedding
from app.models.career import JobEmbedding, ProjectEmbedding


class _FakeDbSession:
    def __init__(self, scalar_results: list[object | None], commit_effects: list[object]) -> None:
        self._scalar_results = scalar_results
        self._commit_effects = commit_effects
        self.added: list[object] = []
        self.refreshed: list[object] = []
        self.rollback_count = 0
        self.commit_count = 0

    async def scalar(self, _statement):
        if not self._scalar_results:
            return None
        return self._scalar_results.pop(0)

    def add(self, instance) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.commit_count += 1
        effect = self._commit_effects.pop(0) if self._commit_effects else None
        if isinstance(effect, Exception):
            raise effect

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def refresh(self, instance) -> None:
        self.refreshed.append(instance)


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT", {}, Exception("duplicate key"))


def test_upsert_project_embedding_recovers_from_insert_race_when_hash_matches() -> None:
    existing = ProjectEmbedding(
        user_id="user-1",
        project_id="project-1",
        embedding_model="model-1",
        content_hash="hash-1",
        embedding=[0.1, 0.2],
    )
    db = _FakeDbSession(
        scalar_results=[None, existing],
        commit_effects=[_integrity_error()],
    )

    result = asyncio.run(
        upsert_project_embedding(
            db=db,
            user_id="user-1",
            project_id="project-1",
            embedding_model="model-1",
            content_hash="hash-1",
            embedding=[0.1, 0.2],
        )
    )

    assert result is existing
    assert db.rollback_count == 1
    assert db.commit_count == 1
    assert db.refreshed == []


def test_upsert_project_embedding_recovers_from_insert_race_when_hash_differs() -> None:
    existing = ProjectEmbedding(
        user_id="user-1",
        project_id="project-1",
        embedding_model="model-1",
        content_hash="stale-hash",
        embedding=[0.0, 0.0],
    )
    db = _FakeDbSession(
        scalar_results=[None, existing],
        commit_effects=[_integrity_error(), None],
    )

    result = asyncio.run(
        upsert_project_embedding(
            db=db,
            user_id="user-1",
            project_id="project-1",
            embedding_model="model-1",
            content_hash="new-hash",
            embedding=[0.9, 0.1],
        )
    )

    assert result is existing
    assert result.content_hash == "new-hash"
    assert result.embedding == [0.9, 0.1]
    assert db.rollback_count == 1
    assert db.commit_count == 2
    assert db.refreshed == [existing]


def test_upsert_job_embedding_recovers_from_insert_race_when_hash_matches() -> None:
    existing = JobEmbedding(
        user_id="user-1",
        job_id="job-1",
        embedding_model="model-1",
        content_hash="hash-1",
        embedding=[0.3, 0.7],
    )
    db = _FakeDbSession(
        scalar_results=[None, existing],
        commit_effects=[_integrity_error()],
    )

    result = asyncio.run(
        upsert_job_embedding(
            db=db,
            user_id="user-1",
            job_id="job-1",
            embedding_model="model-1",
            content_hash="hash-1",
            embedding=[0.3, 0.7],
        )
    )

    assert result is existing
    assert db.rollback_count == 1
    assert db.commit_count == 1
    assert db.refreshed == []


def test_upsert_job_embedding_recovers_from_insert_race_when_hash_differs() -> None:
    existing = JobEmbedding(
        user_id="user-1",
        job_id="job-1",
        embedding_model="model-1",
        content_hash="stale-hash",
        embedding=[0.0, 0.0],
    )
    db = _FakeDbSession(
        scalar_results=[None, existing],
        commit_effects=[_integrity_error(), None],
    )

    result = asyncio.run(
        upsert_job_embedding(
            db=db,
            user_id="user-1",
            job_id="job-1",
            embedding_model="model-1",
            content_hash="new-hash",
            embedding=[0.8, 0.2],
        )
    )

    assert result is existing
    assert result.content_hash == "new-hash"
    assert result.embedding == [0.8, 0.2]
    assert db.rollback_count == 1
    assert db.commit_count == 2
    assert db.refreshed == [existing]
