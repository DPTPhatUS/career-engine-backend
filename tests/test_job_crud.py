import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

from app.crud.job import apply_job_expiration, create_job, list_jobs_by_user_id, update_job


def test_apply_job_expiration_marks_overdue_active_job_expired() -> None:
    job = SimpleNamespace(stage="interviewing", deadline=date.today() - timedelta(days=1))

    changed = apply_job_expiration(job)

    assert changed is True
    assert job.stage == "expired"


def test_apply_job_expiration_preserves_terminal_stage() -> None:
    job = SimpleNamespace(stage="offer", deadline=date.today() - timedelta(days=1))

    changed = apply_job_expiration(job)

    assert changed is False
    assert job.stage == "offer"


def test_apply_job_expiration_does_not_restore_expired_job_with_future_deadline() -> None:
    job = SimpleNamespace(stage="expired", deadline=date.today() + timedelta(days=1))

    changed = apply_job_expiration(job)

    assert changed is False
    assert job.stage == "expired"


def test_create_job_auto_expires_past_deadline() -> None:
    class FakeDb:
        async def scalar(self, statement):
            return None

        def add(self, job):
            self.job = job

        async def commit(self):
            pass

        async def refresh(self, job):
            pass

    db = FakeDb()

    job = asyncio.run(
        create_job(
            db,
            "user-1",
            {
                "company_id": "company-1",
                "title": "Backend Engineer",
                "job_description": "Build backend services",
                "job_requirements": "FastAPI, PostgreSQL",
                "stage": "applied",
                "deadline": date.today() - timedelta(days=1),
            },
            None,
        )
    )

    assert job.stage == "expired"


def test_update_job_auto_expires_past_deadline() -> None:
    class FakeDb:
        async def commit(self):
            pass

        async def refresh(self, job):
            pass

    job = SimpleNamespace(stage="interviewing", deadline=None)

    updated = asyncio.run(update_job(FakeDb(), job, {"deadline": date.today() - timedelta(days=1)}))

    assert updated.stage == "expired"


def test_list_jobs_auto_expires_all_overdue_active_jobs() -> None:
    jobs = [
        SimpleNamespace(stage="saved", deadline=date.today() - timedelta(days=1)),
        SimpleNamespace(stage="applied", deadline=date.today() - timedelta(days=2)),
        SimpleNamespace(stage="offer", deadline=date.today() - timedelta(days=3)),
    ]

    class FakeDb:
        def __init__(self):
            self.commit_count = 0

        async def scalars(self, statement):
            return jobs

        async def commit(self):
            self.commit_count += 1

    db = FakeDb()

    result = asyncio.run(list_jobs_by_user_id(db, "user-1"))

    assert [job.stage for job in result] == ["expired", "expired", "offer"]
    assert db.commit_count == 1
