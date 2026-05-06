from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.project import list_projects_by_ids
from app.services.github_loader import (
    GithubLoaderError,
    RepoSnapshot,
    fetch_repo_snapshot,
    load_repo_context,
    parse_github_repo_url,
)

_SYSTEM_PROMPT = """
You generate resume-ready project summaries from repository evidence.
Return only valid JSON with this exact shape:
{
  "tech_stack": "comma-separated technologies",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}
Rules:
- Use only technologies and accomplishments supported by the repository context.
- Keep tech_stack concise and deduplicated.
- Produce exactly 3 accomplishment bullets.
- Bullets must be impact-oriented and written in past tense.
- Do not include markdown or extra keys.
""".strip()

_TAILOR_SYSTEM_PROMPT = """
You tailor resume-ready project descriptions for a specific job posting.
Return only valid JSON with this exact shape:
{
  "tech_stack": "comma-separated technologies",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}
Rules:
- Use only technologies and accomplishments grounded in repository evidence.
- Adapt wording toward the target role and requirements.
- Produce exactly 3 impact-oriented bullets in past tense.
- Keep claims concrete, concise, and ATS-friendly.
- Do not include markdown or extra keys.
""".strip()


async def autofill_project_from_github(github_url: str, settings: Settings) -> dict[str, Any]:
    coordinates = parse_github_repo_url(github_url)
    snapshot = await fetch_repo_snapshot(coordinates, settings)
    code_context = await load_repo_context(snapshot, settings)
    tech_stack, bullets = await generate_project_summary(snapshot, code_context, settings)

    return {
        "title": snapshot.title,
        "date_range": snapshot.date_range,
        "github_url": snapshot.html_url,
        "tech_stack": tech_stack,
        "bullets": bullets,
    }


async def generate_project_summary(
    snapshot: RepoSnapshot,
    code_context: str,
    settings: Settings,
) -> tuple[str, list[str]]:
    chat_model = _build_chat_model(settings)
    user_prompt = _build_user_prompt(snapshot, code_context)
    response = await _invoke_chat_model(
        chat_model,
        _SYSTEM_PROMPT,
        user_prompt,
        "LLM generation failed while preparing project autofill suggestions.",
    )

    raw_text = _message_to_text(response)
    return normalize_generation_output(raw_text, snapshot.stack_fallback, snapshot.title)


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

    chat_model = _build_chat_model(settings)
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
                chat_model=chat_model,
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
    chat_model: Any,
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
        code_context = await load_repo_context(snapshot, settings)
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
            code_context=code_context,
            job_title=job_title,
            job_description=job_description,
            job_requirements=job_requirements,
            company_name=company_name,
            company_overview=company_overview,
            chat_model=chat_model,
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
    code_context: str,
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None = None,
    company_overview: str | None = None,
    chat_model: Any,
) -> tuple[str, list[str]]:
    user_prompt = _build_job_tailor_user_prompt(
        snapshot=snapshot,
        project_title=project_title,
        project_date_range=project_date_range,
        code_context=code_context,
        job_title=job_title,
        job_description=job_description,
        job_requirements=job_requirements,
        company_name=company_name,
        company_overview=company_overview,
    )

    response = await _invoke_chat_model(
        chat_model,
        _TAILOR_SYSTEM_PROMPT,
        user_prompt,
        "LLM generation failed while tailoring project suggestions to the job.",
    )

    raw_text = _message_to_text(response)
    fallback_stack = _merge_stack_fallback(existing_tech_stack, snapshot.stack_fallback)
    normalized_title = project_title.strip() if project_title.strip() else snapshot.title
    return normalize_generation_output(
        raw_text,
        fallback_stack,
        normalized_title,
        fallback_bullets=existing_bullets,
    )


def normalize_generation_output(
    raw_text: str,
    fallback_stack: list[str],
    repo_title: str,
    fallback_bullets: list[str] | None = None,
) -> tuple[str, list[str]]:
    payload = _extract_json_payload(raw_text)

    tech_stack = _normalize_tech_stack(payload.get("tech_stack"), fallback_stack)
    bullets = _normalize_bullets(payload.get("bullets"), repo_title, fallback_bullets)

    return tech_stack, bullets


def _build_chat_model(settings: Settings):
    provider = settings.project_autofill_llm_provider.lower().strip()

    if provider == "mistral":
        if not settings.mistral_api_key:
            raise GithubLoaderError(
                "MISTRAL_API_KEY is not configured for project autofill.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            from langchain_mistralai import ChatMistralAI
        except Exception as exc:  # noqa: BLE001
            raise GithubLoaderError(
                "langchain-mistralai is not installed.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

        return ChatMistralAI(
            model=settings.project_autofill_mistral_model,
            api_key=settings.mistral_api_key,
            temperature=settings.project_autofill_llm_temperature,
            timeout=settings.project_autofill_llm_timeout_seconds,
            max_retries=2,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise GithubLoaderError(
                "OPENAI_API_KEY is not configured for project autofill.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            from langchain_openai import ChatOpenAI
        except Exception as exc:  # noqa: BLE001
            raise GithubLoaderError(
                "langchain-openai is not installed.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

        return ChatOpenAI(
            model=settings.project_autofill_openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.project_autofill_llm_temperature,
            timeout=settings.project_autofill_llm_timeout_seconds,
            max_retries=2,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise GithubLoaderError(
                "GEMINI_API_KEY is not configured for project autofill.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except Exception as exc:  # noqa: BLE001
            raise GithubLoaderError(
                "langchain-google-genai is not installed.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

        return ChatGoogleGenerativeAI(
            model=settings.project_autofill_gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.project_autofill_llm_temperature,
            timeout=settings.project_autofill_llm_timeout_seconds,
            max_retries=2,
        )

    raise GithubLoaderError(
        "Unsupported PROJECT_AUTOFILL_LLM_PROVIDER value.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _build_user_prompt(snapshot: RepoSnapshot, code_context: str) -> str:
    readme_excerpt = (snapshot.readme_text or "").strip()[:5000]
    code_excerpt = code_context.strip()[: max(0, 120000)]
    fallback_stack = ", ".join(snapshot.stack_fallback)

    return (
        "Repository metadata:\n"
        f"- Name: {snapshot.coordinates.owner}/{snapshot.coordinates.repo}\n"
        f"- Default branch: {snapshot.default_branch}\n"
        f"- Existing title candidate: {snapshot.title}\n"
        f"- Date range candidate: {snapshot.date_range}\n"
        f"- Fallback stack hints: {fallback_stack}\n\n"
        "README excerpt:\n"
        f"{readme_excerpt or '(No README available)'}\n\n"
        "Code excerpt:\n"
        f"{code_excerpt or '(No code excerpt available)'}\n"
    )


def _build_job_tailor_user_prompt(
    *,
    snapshot: RepoSnapshot,
    project_title: str,
    project_date_range: str,
    code_context: str,
    job_title: str,
    job_description: str,
    job_requirements: str,
    company_name: str | None,
    company_overview: str | None,
) -> str:
    readme_excerpt = (snapshot.readme_text or "").strip()[:5000]
    code_excerpt = code_context.strip()[: max(0, 120000)]
    fallback_stack = ", ".join(snapshot.stack_fallback) if snapshot.stack_fallback else "(No stack hints)"

    company_block = ""
    if company_name or company_overview:
        overview_text = company_overview or "(No overview provided)"
        name_line = f"- Company name: {company_name}\n" if company_name else ""
        company_block = (
            "Company context:\n"
            f"{name_line}"
            f"- Company overview:\n{overview_text}\n\n"
        )

    return (
        "Job:\n"
        f"- Job title: {job_title}\n"
        f"- Job description:\n{job_description}\n\n"
        f"- Job requirements:\n{job_requirements}\n\n"
        f"{company_block}"
        "Project profile:\n"
        f"- Project title: {project_title}\n"
        f"- Date range: {project_date_range}\n"
        "Repository evidence:\n"
        f"- Name: {snapshot.coordinates.owner}/{snapshot.coordinates.repo}\n"
        f"- Default branch: {snapshot.default_branch}\n"
        f"- Fallback stack hints: {fallback_stack}\n\n"
        "README excerpt:\n"
        f"{readme_excerpt or '(No README available)'}\n\n"
        "Code excerpt:\n"
        f"{code_excerpt or '(No code excerpt available)'}\n"
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


async def _invoke_chat_model(
    chat_model: Any,
    system_prompt: str,
    user_prompt: str,
    failure_detail: str,
) -> Any:
    try:
        response = await asyncio.to_thread(
            chat_model.invoke,
            [("system", system_prompt), ("human", user_prompt)],
        )
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(failure_detail, status.HTTP_502_BAD_GATEWAY) from exc

    return response


def _message_to_text(message: Any) -> str:
    if hasattr(message, "text"):
        text_value = getattr(message, "text")
        if isinstance(text_value, str) and text_value.strip():
            return text_value

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str):
                    parts.append(block_text)
        return "\n".join(parts)

    return str(content)


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
    candidates: list[str] = []

    if isinstance(raw_bullets, str):
        candidates.extend(line.strip() for line in raw_bullets.splitlines() if line.strip())
    elif isinstance(raw_bullets, list):
        candidates.extend(str(item).strip() for item in raw_bullets if str(item).strip())

    def _clean_bullet_candidates(items: list[str]) -> list[str]:
        cleaned_items: list[str] = []
        seen_items: set[str] = set()
        for raw_item in items:
            cleaned = re.sub(r"^[-*\d\.)\s]+", "", str(raw_item)).strip()
            if not cleaned:
                continue
            cleaned = cleaned.rstrip(".").strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen_items:
                continue
            seen_items.add(key)
            cleaned_items.append(_finalize_sentence(cleaned))
        return cleaned_items

    cleaned_bullets = _clean_bullet_candidates(candidates)

    fallback_candidates: list[str] = []
    if not cleaned_bullets and fallback_bullets:
        fallback_candidates = _clean_bullet_candidates(list(fallback_bullets))

    fallback = [
        _finalize_sentence(
            f"Built and shipped {repo_title} capabilities through modular backend and frontend components"
        ),
        _finalize_sentence(
            f"Implemented maintainable architecture and tooling to improve {repo_title} reliability and developer velocity"
        ),
        _finalize_sentence(
            "Enhanced project quality by iterating on features, fixes, and technical documentation across the repository"
        ),
    ]

    result: list[str] = []
    primary_candidates = cleaned_bullets or fallback_candidates
    for item in primary_candidates + fallback:
        key = item.lower()
        if key in {existing.lower() for existing in result}:
            continue
        result.append(item)
        if len(result) == 3:
            break

    return result


def _finalize_sentence(text: str) -> str:
    sentence = re.sub(r"\s+", " ", text).strip()
    if sentence and sentence[-1] not in {".", "!", "?"}:
        sentence = f"{sentence}."
    return sentence
