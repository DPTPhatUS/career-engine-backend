from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import status

from app.core.config import Settings
from app.services.github_loader import GithubLoaderError, RepoSnapshot


def build_codexpert_agent(settings: Settings):
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

    workspace_dir = Path(settings.project_autofill_agent_workspace_dir).expanduser()
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


async def query_codexpert(agent: Any, snapshot: RepoSnapshot, question: str, operation: str) -> str:
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


def merge_stack_fallback(existing_tech_stack: str | None, snapshot_stack: list[str]) -> list[str]:
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


def fallback_project_title(repo_name: str) -> str:
    fallback = re.sub(r"[-_]+", " ", repo_name).strip()
    return " ".join(word.capitalize() for word in fallback.split()) if fallback else repo_name


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
