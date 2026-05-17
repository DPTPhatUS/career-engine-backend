from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.project import list_projects_by_ids
from app.services.github_loader import (
    GithubLoaderError,
    RepoSnapshot,
    fetch_repo_snapshot,
    parse_github_repo_url,
)

_AUTOFILL_QUESTION = """
Analyze this repository and generate resume-ready project metadata.
Return only valid JSON with this exact shape:
{
  "title": "short project title",
  "tech_stack": "comma-separated technologies",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}
Rules:
- Use repository evidence from code, docs, package files, and configuration.
- Generate the title from repository evidence, not from the GitHub URL alone.
- Keep tech_stack concise and deduplicated.
- Produce exactly 3 accomplishment bullets.
- Bullets must be impact-oriented and written in past tense.
- Do not include markdown, citations, or extra keys.
""".strip()

_TAILOR_QUESTION = """
Analyze this repository and tailor its resume project description for the target job.
Return only valid JSON with this exact shape:
{
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


async def autofill_project_from_github(github_url: str, settings: Settings) -> dict[str, Any]:
    coordinates = parse_github_repo_url(github_url)
    snapshot = await fetch_repo_snapshot(coordinates, settings)
    title, tech_stack, bullets = await generate_project_summary(snapshot, settings)

    return {
        "title": title,
        "date_range": snapshot.date_range,
        "github_url": snapshot.html_url,
        "tech_stack": tech_stack,
        "bullets": bullets,
    }


async def generate_project_summary(
    snapshot: RepoSnapshot,
    settings: Settings,
    codexpert_agent: Any | None = None,
) -> tuple[str, str, list[str]]:
    agent = codexpert_agent or _build_codexpert_agent(settings)
    question = _build_autofill_question(snapshot)
    raw_text = await _query_codexpert(agent, snapshot, question, "project_autofill")
    fallback_title = _fallback_project_title(snapshot.coordinates.repo)
    title, tech_stack, bullets = normalize_project_generation_output(
        raw_text,
        fallback_title=fallback_title,
        fallback_stack=[],
    )
    return title, tech_stack, bullets


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
        raise GithubLoaderError(
            f"Selected projects were not found for current user: {missing_text}.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    codexpert_agent = _build_codexpert_agent(settings)
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
                codexpert_agent=codexpert_agent,
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
        snapshot = await fetch_repo_snapshot(coordinates, settings)
    except GithubLoaderError as exc:
        return None, {
            "project_id": project.id,
            "reason_code": "github_scan_failed",
            "detail": exc.detail,
        }

    try:
        tech_stack, bullets = await generate_job_tailored_project_summary(
            snapshot=snapshot,
            project_title=project.title,
            project_date_range=project.date_range,
            existing_tech_stack=project.tech_stack,
            existing_bullets=project.bullets or [],
            job_title=job_title,
            job_description=job_description,
            job_requirements=job_requirements,
            company_name=company_name,
            company_overview=company_overview,
            codexpert_agent=codexpert_agent,
        )
    except GithubLoaderError as exc:
        return None, {
            "project_id": project.id,
            "reason_code": "generation_failed",
            "detail": exc.detail,
        }

    return {
        "project_id": project.id,
        "title": project.title,
        "date_range": project.date_range,
        "github_url": snapshot.html_url,
        "tech_stack": tech_stack,
        "bullets": bullets,
    }, None


async def generate_job_tailored_project_summary(
    *,
    snapshot: RepoSnapshot,
    project_title: str,
    project_date_range: str,
    existing_tech_stack: str | None,
    existing_bullets: list[str],
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None = None,
    company_overview: str | None = None,
    codexpert_agent: Any,
) -> tuple[str, list[str]]:
    question = _build_job_tailor_question(
        project_title=project_title,
        project_date_range=project_date_range,
        job_title=job_title,
        job_description=job_description,
        job_requirements=job_requirements,
        company_name=company_name,
        company_overview=company_overview,
    )
    raw_text = await _query_codexpert(codexpert_agent, snapshot, question, "project_tailor")
    fallback_stack = _merge_stack_fallback(existing_tech_stack, [])
    normalized_title = project_title.strip() if project_title.strip() else _fallback_project_title(snapshot.coordinates.repo)
    return normalize_generation_output(
        raw_text,
        fallback_stack,
        normalized_title,
        fallback_bullets=existing_bullets,
    )


def normalize_project_generation_output(
    raw_text: str,
    *,
    fallback_title: str,
    fallback_stack: list[str],
    fallback_bullets: list[str] | None = None,
) -> tuple[str, str, list[str]]:
    payload = _extract_json_payload(raw_text)
    title = _normalize_title(payload.get("title"), fallback_title)
    tech_stack = _normalize_tech_stack(payload.get("tech_stack"), fallback_stack)
    bullets = _normalize_bullets(payload.get("bullets"), title, fallback_bullets)
    return title, tech_stack, bullets


def normalize_generation_output(
    raw_text: str,
    fallback_stack: list[str],
    repo_title: str,
    fallback_bullets: list[str] | None = None,
) -> tuple[str, list[str]]:
    _title, tech_stack, bullets = normalize_project_generation_output(
        raw_text,
        fallback_title=repo_title,
        fallback_stack=fallback_stack,
        fallback_bullets=fallback_bullets,
    )
    return tech_stack, bullets


def _build_codexpert_agent(settings: Settings):
    try:
        from codexpert import AgentConfig, CodexpertAgent
        from codexpert.core.config import LLMConfig, LLMProvider
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(
            "codexpert is not installed.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    provider = settings.project_autofill_llm_provider.lower().strip()
    try:
        llm_provider = LLMProvider(provider)
    except ValueError as exc:
        raise GithubLoaderError(
            "Unsupported PROJECT_AUTOFILL_LLM_PROVIDER value.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    model_by_provider = {
        "mistral": settings.project_autofill_mistral_model,
        "openai": settings.project_autofill_openai_model,
        "gemini": settings.project_autofill_gemini_model,
    }
    api_key_env_by_provider = {
        "mistral": "MISTRAL_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    api_key_value_by_provider = {
        "mistral": settings.mistral_api_key,
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
    }

    if not api_key_value_by_provider[provider]:
        raise GithubLoaderError(
            f"{api_key_env_by_provider[provider]} is not configured for project autofill.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    workspace_dir = Path(settings.project_autofill_codexpert_workspace_dir).expanduser()
    config = AgentConfig(
        workspace_dir=workspace_dir,
        top_k=settings.project_autofill_agent_top_k,
        max_iterations=settings.project_autofill_agent_max_iterations,
        llm=LLMConfig(
            provider=llm_provider,
            model=model_by_provider[provider],
            api_key_env=api_key_env_by_provider[provider],
            temperature=settings.project_autofill_llm_temperature,
            timeout_s=settings.project_autofill_llm_timeout_seconds,
        ),
    )
    return CodexpertAgent(config)


async def _query_codexpert(agent: Any, snapshot: RepoSnapshot, question: str, operation: str) -> str:
    request = _build_codexpert_request(snapshot, question, operation)
    try:
        response = await agent.async_query(request)
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(
            "Codexpert generation failed while preparing project suggestions.",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    answer = getattr(response, "answer", "")
    return answer if isinstance(answer, str) else str(answer)


def _build_codexpert_request(snapshot: RepoSnapshot, question: str, operation: str) -> Any:
    repo_id = _build_codexpert_repo_id(snapshot)
    try:
        from codexpert import QueryRequest, RepoSpec

        repo = RepoSpec(repo_id=repo_id, source=snapshot.html_url, ref=snapshot.default_branch)
        return QueryRequest(
            repo_id=repo_id,
            question=question,
            top_k=5,
            repo=repo,
            metadata={"operation": operation},
        )
    except Exception:  # noqa: BLE001
        repo = SimpleNamespace(repo_id=repo_id, source=snapshot.html_url, ref=snapshot.default_branch)
        return SimpleNamespace(
            repo_id=repo_id,
            question=question,
            top_k=5,
            history=[],
            repo=repo,
            metadata={"operation": operation},
        )


def _build_codexpert_repo_id(snapshot: RepoSnapshot) -> str:
    raw = (
        f"{snapshot.coordinates.owner}-{snapshot.coordinates.repo}-"
        f"{snapshot.default_branch}-{snapshot.latest_commit_sha or 'latest'}"
    )
    return re.sub(r"[^A-Za-z0-9-]+", "-", raw).strip("-").lower() or "repo"


def _build_autofill_question(snapshot: RepoSnapshot) -> str:
    return (
        f"{_AUTOFILL_QUESTION}\n\n"
        "Repository:\n"
        f"- URL: {snapshot.html_url}\n"
        f"- Owner: {snapshot.coordinates.owner}\n"
        f"- Name: {snapshot.coordinates.repo}\n"
        f"- Default branch: {snapshot.default_branch}\n"
    )


def _build_job_tailor_question(
    *,
    project_title: str,
    project_date_range: str,
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
        "Existing project profile:\n"
        f"- Project title: {project_title}\n"
        f"- Date range: {project_date_range}\n\n"
        "Target job:\n"
        f"- Job title: {job_title}\n"
        f"- Job description:\n{job_description}\n\n"
        f"- Job requirements:\n{job_requirements}\n\n"
        f"{company_block}"
    )


def _merge_stack_fallback(existing_tech_stack: str | None, snapshot_stack: list[str]) -> list[str]:
    values: list[str] = []

    if existing_tech_stack:
        values.extend(part.strip() for part in re.split(r",|\n|\|", existing_tech_stack) if part.strip())
    values.extend(snapshot_stack)

    seen: set[str] = set()
    deduplicated: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(value)

    return deduplicated


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        return {}

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _normalize_title(raw_title: Any, fallback_title: str) -> str:
    if isinstance(raw_title, str):
        cleaned = re.sub(r"\s+", " ", raw_title.strip())
        if cleaned:
            return cleaned[:120]
    return fallback_title


def _normalize_tech_stack(raw_stack: Any, fallback_stack: list[str]) -> str:
    candidates: list[str] = []

    if isinstance(raw_stack, list):
        candidates.extend(str(item) for item in raw_stack)
    elif isinstance(raw_stack, str):
        candidates.extend(re.split(r",|\n|\|", raw_stack))

    if not candidates:
        candidates.extend(fallback_stack)

    normalized: list[str] = []
    seen: set[str] = set()

    for item in candidates:
        cleaned = str(item).strip().strip(".")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)

    if not normalized:
        normalized = ["Git", "Software Development"]

    return ", ".join(normalized[:10])


def _normalize_bullets(
    raw_bullets: Any,
    repo_title: str,
    fallback_bullets: list[str] | None = None,
) -> list[str]:
    bullets: list[str] = []

    if isinstance(raw_bullets, list):
        bullets.extend(str(item) for item in raw_bullets)
    elif isinstance(raw_bullets, str):
        bullets.extend(line for line in raw_bullets.splitlines() if line.strip())

    if not bullets and fallback_bullets:
        bullets.extend(fallback_bullets)

    normalized: list[str] = []
    for bullet in bullets:
        cleaned = re.sub(r"^\s*[-*•\d.)]+\s*", "", str(bullet).strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            continue
        if cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        normalized.append(cleaned)
        if len(normalized) == 3:
            break

    while len(normalized) < 3:
        normalized.append(f"Built and refined {repo_title} using repository-backed implementation evidence.")

    return normalized[:3]


def _fallback_project_title(repo_name: str) -> str:
    fallback = re.sub(r"[-_]+", " ", repo_name).strip()
    return " ".join(word.capitalize() for word in fallback.split()) if fallback else repo_name
