from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import status

from app.core.config import Settings
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

    try:
        response = await asyncio.to_thread(
            chat_model.invoke,
            [("system", _SYSTEM_PROMPT), ("human", user_prompt)],
        )
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(
            "LLM generation failed while preparing project autofill suggestions.",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    raw_text = _message_to_text(response)
    return normalize_generation_output(raw_text, snapshot.stack_fallback, snapshot.title)


def normalize_generation_output(
    raw_text: str,
    fallback_stack: list[str],
    repo_title: str,
) -> tuple[str, list[str]]:
    payload = _extract_json_payload(raw_text)

    tech_stack = _normalize_tech_stack(payload.get("tech_stack"), fallback_stack)
    bullets = _normalize_bullets(payload.get("bullets"), repo_title)

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


def _normalize_bullets(raw_bullets: Any, repo_title: str) -> list[str]:
    candidates: list[str] = []

    if isinstance(raw_bullets, str):
        candidates.extend(line.strip() for line in raw_bullets.splitlines() if line.strip())
    elif isinstance(raw_bullets, list):
        candidates.extend(str(item).strip() for item in raw_bullets if str(item).strip())

    cleaned_bullets: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        cleaned = re.sub(r"^[-*\d\.)\s]+", "", item).strip()
        if not cleaned:
            continue
        cleaned = cleaned.rstrip(".").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned_bullets.append(_finalize_sentence(cleaned))

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
    for item in cleaned_bullets + fallback:
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
