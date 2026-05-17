from __future__ import annotations

import asyncio
from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.project import list_projects_by_ids
from app.services import codexpert_agent as codexpert_agent_service
from app.services.github_loader import (
    GithubError,
    RepoMetadata,
    fetch_repo_metadata,
    parse_github_repo_url,
)

_TAILOR_QUESTION = """
Analyze this repository and generate resume-ready project description for the target job.
Return only valid JSON with this exact shape:
{
  "title": "short project title",
  "tech_stack": "comma-separated technologies",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}
Rules:
- Use repository evidence from code, docs, package files, and configuration.
- Adapt wording toward the target role and requirements.
- Produce exactly 3 impact-oriented bullets in past tense.
- Keep claims concrete, concise, and ATS-friendly.
- Do not include markdown, citations, or extra keys.
""".strip()


async def tailor_projects_for_job(
    *,
    db: AsyncSession,
    user_id: str,
    project_ids: list[str],
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None = None,
    company_overview: str | None = None,
    settings: Settings,
) -> dict[str, Any]:
    projects = await list_projects_by_ids(db, user_id, project_ids)
    if len(projects) != len(project_ids):
        found_ids = {project.id for project in projects}
        missing_ids = [project_id for project_id in project_ids if project_id not in found_ids]
        missing_text = ", ".join(missing_ids)
        raise GithubError(
            f"Selected projects were not found for current user: {missing_text}.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    agent = codexpert_agent_service.build_codexpert_agent(settings)
    semaphore = asyncio.Semaphore(2)

    async def _run(project) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        async with semaphore:
            return await _tailor_single_project(
                project=project,
                job_title=job_title,
                job_description=job_description,
                job_requirements=job_requirements,
                company_name=company_name,
                company_overview=company_overview,
                codexpert_agent=agent,
                settings=settings,
            )

    results = await asyncio.gather(*[_run(project) for project in projects])

    tailored_projects: list[dict[str, Any]] = []
    skipped_projects: list[dict[str, str]] = []
    for tailored_project, skipped_warning in results:
        if tailored_project:
            tailored_projects.append(tailored_project)
        if skipped_warning:
            skipped_projects.append(skipped_warning)

    return {
        "tailored_projects": tailored_projects,
        "skipped_projects": skipped_projects,
    }


async def _tailor_single_project(
    *,
    project,
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None,
    company_overview: str | None,
    codexpert_agent: Any,
    settings: Settings,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    github_url = str(project.github_url).strip() if project.github_url else ""
    if not github_url:
        return None, {
            "project_id": project.id,
            "reason_code": "missing_github_url",
            "detail": "Project has no GitHub URL, so tailoring was skipped.",
        }

    try:
        coordinates = parse_github_repo_url(github_url)
        repo_metadata = await fetch_repo_metadata(coordinates, settings)
    except GithubError as exc:
        return None, {
            "project_id": project.id,
            "reason_code": "github_scan_failed",
            "detail": exc.detail,
        }

    try:
        title, tech_stack, bullets = await generate_job_tailored_project_summary(
            repo_metadata=repo_metadata,
            job_title=job_title,
            job_description=job_description,
            job_requirements=job_requirements,
            company_name=company_name,
            company_overview=company_overview,
            codexpert_agent=codexpert_agent,
        )
    except GithubError as exc:
        return None, {
            "project_id": project.id,
            "reason_code": "generation_failed",
            "detail": exc.detail,
        }

    return {
        "project_id": project.id,
        "title": title,
        "date_range": project.date_range,
        "github_url": repo_metadata.html_url,
        "tech_stack": tech_stack,
        "bullets": bullets,
    }, None


async def generate_job_tailored_project_summary(
    *,
    repo_metadata: RepoMetadata,
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None = None,
    company_overview: str | None = None,
    codexpert_agent: Any,
) -> tuple[str, str, list[str]]:
    question = _build_job_tailor_question(
        job_title=job_title,
        job_description=job_description,
        job_requirements=job_requirements,
        company_name=company_name,
        company_overview=company_overview,
    )
    raw_text = await codexpert_agent_service.query_codexpert(codexpert_agent, repo_metadata, question, "project_tailor")
    title, tech_stack, bullets = codexpert_agent_service.parse_project_generation_output(raw_text)
    return title, tech_stack, bullets


def _build_job_tailor_question(
    *,
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None,
    company_overview: str | None,
) -> str:
    company_block = ""
    if company_name or company_overview:
        company_block = (
            "Company context:\n"
            f"- Company name: {company_name or '(not provided)'}\n"
            f"- Company overview:\n{company_overview or '(not provided)'}\n\n"
        )

    return (
        f"{_TAILOR_QUESTION}\n\n"
        "Target job:\n"
        f"- Job title: {job_title}\n"
        f"- Job description:\n{job_description}\n\n"
        f"- Job requirements:\n{job_requirements}\n\n"
        f"{company_block}"
    )
