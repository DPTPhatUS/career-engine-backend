import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import status
from pydantic import ValidationError

from app.schemas.project import TailorProjectsRequest
from app.services.project_autofill import (
    generate_project_summary,
    generate_job_tailored_project_summary,
    normalize_generation_output,
    tailor_projects_for_job,
)
from app.services.github_loader import (
    GithubLoaderError,
    RepoCoordinates,
    RepoSnapshot,
    format_project_date_range,
    parse_github_repo_url,
)


def test_parse_github_repo_url_supports_git_suffix() -> None:
    coordinates = parse_github_repo_url("https://github.com/example-org/career-engine.git")
    assert coordinates.owner == "example-org"
    assert coordinates.repo == "career-engine"


def test_parse_github_repo_url_rejects_non_github_host() -> None:
    with pytest.raises(GithubLoaderError) as exc:
        parse_github_repo_url("https://gitlab.com/example/repo")

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_format_project_date_range_uses_present_for_current_month() -> None:
    start_date = datetime(2025, 1, 12, tzinfo=timezone.utc)
    end_date = datetime(2026, 4, 3, tzinfo=timezone.utc)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)

    assert format_project_date_range(start_date, end_date, now=now) == "Jan 2025 - Present"


def test_normalize_generation_output_returns_exactly_three_bullets() -> None:
    raw_text = """
    {
      "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Python"],
      "bullets": [
        "Built async APIs",
        "Improved test coverage",
        "Automated deployment",
        "Extra bullet"
      ]
    }
    """

    tech_stack, bullets = normalize_generation_output(raw_text, ["Git"], "Career Engine")

    assert tech_stack == "Python, FastAPI, PostgreSQL"
    assert len(bullets) == 3
    assert bullets[0].endswith(".")


def test_normalize_generation_output_falls_back_when_json_invalid() -> None:
    tech_stack, bullets = normalize_generation_output("invalid", ["FastAPI", "PostgreSQL"], "Career Engine")

    assert tech_stack == "FastAPI, PostgreSQL"
    assert len(bullets) == 3


def test_normalize_generation_output_uses_fallback_bullets_when_empty() -> None:
    raw_text = '{"tech_stack": "Python", "bullets": []}'

    tech_stack, bullets = normalize_generation_output(
        raw_text,
        ["Git"],
        "Career Engine",
        fallback_bullets=[
            "Delivered reliable project workflows",
            "Improved resume data quality",
            "Automated project status updates",
        ],
    )

    assert tech_stack == "Python"
    assert bullets == [
        "Delivered reliable project workflows.",
        "Improved resume data quality.",
        "Automated project status updates.",
    ]


def test_normalize_generation_output_ignores_fallback_bullets_when_present() -> None:
    raw_text = '{"tech_stack": "Python", "bullets": ["Built async APIs"]}'
    fallback_bullets = [
        "Delivered reliable project workflows",
        "Improved resume data quality",
        "Automated project status updates",
    ]

    _tech_stack, bullets = normalize_generation_output(
        raw_text,
        ["Git"],
        "Career Engine",
        fallback_bullets=fallback_bullets,
    )

    assert len(bullets) == 3
    assert bullets[0] == "Built async APIs."
    assert "Delivered reliable project workflows." not in bullets
    assert "Improved resume data quality." not in bullets
    assert "Automated project status updates." not in bullets


def test_tailor_projects_request_rejects_duplicate_project_ids() -> None:
    with pytest.raises(ValidationError):
        TailorProjectsRequest(
            job_title="Backend Engineer",
            job_description="Build APIs",
            job_requirements="FastAPI, PostgreSQL",
            project_ids=["project-1", "project-1"],
        )


def test_tailor_projects_for_job_skips_missing_github_url(monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="project-1",
        title="Career Engine",
        date_range="Jan 2024 - Present",
        github_url=None,
        tech_stack="FastAPI, PostgreSQL",
        bullets=["Built APIs"],
    )

    async def fake_list_projects_by_ids(db, user_id: str, project_ids: list[str]):
        return [project]

    monkeypatch.setattr("app.services.project_autofill.list_projects_by_ids", fake_list_projects_by_ids)
    monkeypatch.setattr("app.services.project_autofill._build_codexpert_agent", lambda settings: object())

    payload = asyncio.run(
        tailor_projects_for_job(
            db=object(),
            user_id="user-1",
            project_ids=["project-1"],
            job_title="Backend Engineer",
            job_description="Build backend services",
            job_requirements="FastAPI and SQL",
            company_name=None,
            company_overview=None,
            settings=SimpleNamespace(),
        )
    )

    assert payload["tailored_projects"] == []
    assert payload["skipped_projects"] == [
        {
            "project_id": "project-1",
            "reason_code": "missing_github_url",
            "detail": "Project has no GitHub URL, so tailoring was skipped.",
        }
    ]


def test_tailor_projects_for_job_raises_for_missing_project_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = SimpleNamespace(
        id="project-1",
        title="Career Engine",
        date_range="Jan 2024 - Present",
        github_url="https://github.com/org/repo",
        tech_stack="FastAPI, PostgreSQL",
        bullets=["Built APIs"],
    )

    async def fake_list_projects_by_ids(db, user_id: str, project_ids: list[str]):
        return [project]

    monkeypatch.setattr("app.services.project_autofill.list_projects_by_ids", fake_list_projects_by_ids)

    with pytest.raises(GithubLoaderError) as exc:
        asyncio.run(
            tailor_projects_for_job(
                db=object(),
                user_id="user-1",
                project_ids=["project-1", "project-2"],
                job_title="Backend Engineer",
                job_description="Build backend services",
                job_requirements="FastAPI and SQL",
                settings=SimpleNamespace(),
            )
        )

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "project-2" in exc.value.detail


def test_tailor_projects_for_job_returns_mixed_success(monkeypatch: pytest.MonkeyPatch) -> None:
    project_ok = SimpleNamespace(
        id="project-1",
        title="Career Engine",
        date_range="Jan 2024 - Present",
        github_url="https://github.com/org/repo",
        tech_stack="FastAPI, PostgreSQL",
        bullets=["Built APIs"],
    )
    project_skip = SimpleNamespace(
        id="project-2",
        title="No Repo Project",
        date_range="Feb 2024 - Mar 2024",
        github_url=None,
        tech_stack=None,
        bullets=[],
    )

    async def fake_list_projects_by_ids(db, user_id: str, project_ids: list[str]):
        return [project_ok, project_skip]

    def fake_parse_github_repo_url(github_url: str) -> RepoCoordinates:
        _ = github_url
        return RepoCoordinates(owner="org", repo="repo")

    async def fake_fetch_repo_snapshot(coordinates: RepoCoordinates, settings) -> RepoSnapshot:
        _ = settings
        return RepoSnapshot(
            coordinates=coordinates,
            html_url="https://github.com/org/repo",
            date_range="Jan 2024 - Present",
            default_branch="main",
            latest_commit_sha="abc123",
        )

    class FakeCodexpertAgent:
        async def async_query(self, request):
            assert request.repo is not None
            assert request.repo.source == "https://github.com/org/repo"
            return SimpleNamespace(
                answer='{"tech_stack": "Python, FastAPI", "bullets": ["Built APIs", "Improved tests", "Reduced latency"]}'
            )

    monkeypatch.setattr("app.services.project_autofill.list_projects_by_ids", fake_list_projects_by_ids)
    monkeypatch.setattr("app.services.project_autofill.parse_github_repo_url", fake_parse_github_repo_url)
    monkeypatch.setattr("app.services.project_autofill.fetch_repo_snapshot", fake_fetch_repo_snapshot)
    monkeypatch.setattr("app.services.project_autofill._build_codexpert_agent", lambda settings: FakeCodexpertAgent())

    payload = asyncio.run(
        tailor_projects_for_job(
            db=object(),
            user_id="user-1",
            project_ids=["project-1", "project-2"],
            job_title="Backend Engineer",
            job_description="Build backend services",
            job_requirements="FastAPI and SQL",
            company_name="Acme Corp",
            company_overview="Builds developer tooling.",
            settings=SimpleNamespace(),
        )
    )

    assert len(payload["tailored_projects"]) == 1
    assert payload["tailored_projects"][0]["project_id"] == "project-1"
    assert len(payload["tailored_projects"][0]["bullets"]) == 3
    assert payload["skipped_projects"][0]["project_id"] == "project-2"
    assert payload["skipped_projects"][0]["reason_code"] == "missing_github_url"


def test_generate_job_tailored_summary_falls_back_when_json_invalid() -> None:
    class FakeCodexpertAgent:
        async def async_query(self, _request):
            return SimpleNamespace(answer="not-json")

    snapshot = RepoSnapshot(
        coordinates=RepoCoordinates(owner="org", repo="repo"),
        html_url="https://github.com/org/repo",
        date_range="Jan 2024 - Present",
        default_branch="main",
        latest_commit_sha="abc123",
    )

    tech_stack, bullets = asyncio.run(
        generate_job_tailored_project_summary(
            snapshot=snapshot,
            project_title="Career Engine",
            project_date_range="Jan 2024 - Present",
            existing_tech_stack="FastAPI, Python",
            existing_bullets=["Built APIs"],
            job_title="Backend Engineer",
            job_description="Build backend services",
            job_requirements="FastAPI and SQL",
            company_name=None,
            company_overview=None,
            codexpert_agent=FakeCodexpertAgent(),
        )
    )

    assert tech_stack == "FastAPI, Python"
    assert len(bullets) == 3


def test_generate_project_summary_uses_codexpert_title() -> None:
    class FakeCodexpertAgent:
        async def async_query(self, request):
            assert request.repo is not None
            assert request.repo.source == "https://github.com/org/repo"
            assert "title" in request.question
            return SimpleNamespace(
                answer=(
                    '{"title": "Codexpert Career Engine", "tech_stack": "Python, FastAPI", '
                    '"bullets": ["Built APIs", "Improved tests", "Reduced latency"]}'
                )
            )

    snapshot = RepoSnapshot(
        coordinates=RepoCoordinates(owner="org", repo="repo"),
        html_url="https://github.com/org/repo",
        date_range="Jan 2024 - Present",
        default_branch="main",
        latest_commit_sha="abc123",
    )

    title, tech_stack, bullets = asyncio.run(
        generate_project_summary(
            snapshot=snapshot,
            settings=SimpleNamespace(),
            codexpert_agent=FakeCodexpertAgent(),
        )
    )

    assert title == "Codexpert Career Engine"
    assert tech_stack == "Python, FastAPI"
    assert bullets == [
        "Built APIs.",
        "Improved tests.",
        "Reduced latency.",
    ]
