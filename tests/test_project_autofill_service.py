from datetime import datetime, timezone

import pytest
from fastapi import status

from app.services.project_autofill import normalize_generation_output
from app.services.github_loader import (
    GithubLoaderError,
    derive_project_title,
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


def test_derive_project_title_prefers_readme_heading() -> None:
    title = derive_project_title(
        "career-engine",
        "# Career Engine [Backend](https://example.com)\n\nProject details",
    )

    assert title == "Career Engine Backend"


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
