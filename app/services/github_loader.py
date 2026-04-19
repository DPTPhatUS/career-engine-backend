from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import status

from app.core.config import Settings

_SUPPORTED_GITHUB_HOSTS = {"github.com", "www.github.com"}
_IGNORED_PATH_PARTS = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}
_ALLOWED_CODE_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


class GithubLoaderError(Exception):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(slots=True)
class RepoCoordinates:
    owner: str
    repo: str


@dataclass(slots=True)
class RepoSnapshot:
    coordinates: RepoCoordinates
    html_url: str
    title: str
    date_range: str
    readme_text: str
    default_branch: str
    stack_fallback: list[str]


def parse_github_repo_url(github_url: str) -> RepoCoordinates:
    parsed = urlparse(github_url)
    if parsed.scheme not in {"http", "https"}:
        raise GithubLoaderError(
            "GitHub URL must start with http:// or https://.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if parsed.netloc.lower() not in _SUPPORTED_GITHUB_HOSTS:
        raise GithubLoaderError(
            "Only github.com repository URLs are supported.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise GithubLoaderError(
            "GitHub URL must include both owner and repository name.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    owner = path_parts[0].strip()
    repo = path_parts[1].strip()
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise GithubLoaderError(
            "GitHub URL must include both owner and repository name.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return RepoCoordinates(owner=owner, repo=repo)


async def fetch_repo_snapshot(coordinates: RepoCoordinates, settings: Settings) -> RepoSnapshot:
    async with httpx.AsyncClient(timeout=settings.project_autofill_http_timeout_seconds) as client:
        repo_response = await _github_request(client, settings, f"repos/{coordinates.owner}/{coordinates.repo}")
        repo_payload = repo_response.json()

        default_branch = repo_payload.get("default_branch") or "main"
        readme_text = await _fetch_readme_text(client, settings, coordinates)
        start_dt, end_dt = await _fetch_commit_bounds(client, settings, coordinates, default_branch)

    title = derive_project_title(coordinates.repo, readme_text)
    if start_dt is None or end_dt is None:
        created_at = _parse_github_datetime(repo_payload.get("created_at"))
        pushed_at = _parse_github_datetime(repo_payload.get("pushed_at"))
        updated_at = _parse_github_datetime(repo_payload.get("updated_at"))
        start_dt = created_at or updated_at or datetime.now(timezone.utc)
        end_dt = pushed_at or updated_at or start_dt

    stack_fallback = _build_stack_fallback(repo_payload)
    html_url = repo_payload.get("html_url") or f"https://github.com/{coordinates.owner}/{coordinates.repo}"

    return RepoSnapshot(
        coordinates=coordinates,
        html_url=html_url,
        title=title,
        date_range=format_project_date_range(start_dt, end_dt),
        readme_text=readme_text,
        default_branch=default_branch,
        stack_fallback=stack_fallback,
    )


async def load_repo_context(snapshot: RepoSnapshot, settings: Settings) -> str:
    if not settings.github_token:
        raise GithubLoaderError(
            "GITHUB_TOKEN is required to scan repository code for autofill generation.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    loader = _build_github_loader(snapshot.coordinates, snapshot.default_branch, settings)

    try:
        documents = await asyncio.to_thread(loader.load)
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(
            "Failed to scan repository files for autofill generation.",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    return _build_code_context(
        documents,
        max_files=settings.project_autofill_max_files,
        max_chars=settings.project_autofill_max_chars,
    )


def derive_project_title(repo_name: str, readme_text: str) -> str:
    if readme_text:
        lines = readme_text.splitlines()
        first_line = lines[0] if lines else readme_text
        match = re.match(r"^\s*#\s+(.+?)\s*$", first_line)
        if match:
            heading = _clean_markdown_title(match.group(1))
            if heading:
                return heading[:120]

    fallback = re.sub(r"[-_]+", " ", repo_name).strip()
    return " ".join(word.capitalize() for word in fallback.split()) if fallback else repo_name


def format_project_date_range(
    start_date: datetime,
    end_date: datetime,
    now: datetime | None = None,
) -> str:
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    now = now or datetime.now(timezone.utc)
    start_label = start_date.strftime("%b %Y")

    if end_date.year == now.year and end_date.month == now.month:
        end_label = "Present"
    else:
        end_label = end_date.strftime("%b %Y")

    return f"{start_label} - {end_label}"


async def _fetch_readme_text(
    client: httpx.AsyncClient,
    settings: Settings,
    coordinates: RepoCoordinates,
) -> str:
    try:
        readme_response = await _github_request(
            client,
            settings,
            f"repos/{coordinates.owner}/{coordinates.repo}/readme",
        )
    except GithubLoaderError as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return ""
        raise

    payload = readme_response.json()
    encoded_content = payload.get("content")
    if not encoded_content:
        return ""

    try:
        normalized = encoded_content.replace("\n", "")
        return base64.b64decode(normalized).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


async def _fetch_commit_bounds(
    client: httpx.AsyncClient,
    settings: Settings,
    coordinates: RepoCoordinates,
    branch: str,
) -> tuple[datetime | None, datetime | None]:
    try:
        latest_response = await _github_request(
            client,
            settings,
            f"repos/{coordinates.owner}/{coordinates.repo}/commits",
            params={"sha": branch, "per_page": 1},
        )
    except GithubLoaderError as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return None, None
        raise

    latest_items = latest_response.json()
    if not latest_items:
        return None, None

    newest = _parse_commit_datetime(latest_items[0])
    oldest = newest

    last_link = _extract_last_page_link(latest_response.headers.get("Link", ""))
    if last_link:
        try:
            oldest_response = await _github_request(client, settings, last_link, absolute_url=True)
            oldest_items = oldest_response.json()
            if oldest_items:
                parsed_oldest = _parse_commit_datetime(oldest_items[0])
                if parsed_oldest is not None:
                    oldest = parsed_oldest
        except GithubLoaderError:
            pass

    if newest is None or oldest is None:
        return None, None

    return min(oldest, newest), max(oldest, newest)


async def _github_request(
    client: httpx.AsyncClient,
    settings: Settings,
    path_or_url: str,
    *,
    params: dict[str, Any] | None = None,
    absolute_url: bool = False,
) -> httpx.Response:
    url = path_or_url if absolute_url else _build_github_api_url(settings.github_api_base_url, path_or_url)

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as exc:
        raise GithubLoaderError(
            "Unable to reach GitHub API right now.",
            status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if response.status_code < 400:
        return response

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GithubLoaderError(
            "GitHub repository was not found or is not publicly accessible.",
            status.HTTP_404_NOT_FOUND,
        )

    if response.status_code == status.HTTP_403_FORBIDDEN:
        if response.headers.get("x-ratelimit-remaining") == "0":
            raise GithubLoaderError(
                "GitHub API rate limit reached. Please retry later.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        raise GithubLoaderError(
            "GitHub repository is not accessible with the current credentials.",
            status.HTTP_403_FORBIDDEN,
        )

    if response.status_code == status.HTTP_409_CONFLICT:
        raise GithubLoaderError("Repository has no commit history.", status.HTTP_409_CONFLICT)

    if response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        raise GithubLoaderError(
            "GitHub repository request was invalid.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    raise GithubLoaderError(
        f"GitHub API request failed with status {response.status_code}.",
        status.HTTP_502_BAD_GATEWAY,
    )


def _build_github_loader(coordinates: RepoCoordinates, branch: str, settings: Settings):
    try:
        from langchain_community.document_loaders import GithubFileLoader
    except Exception as exc:  # noqa: BLE001
        raise GithubLoaderError(
            "LangChain GitHub loaders are unavailable. Install langchain-community.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    repo_name = f"{coordinates.owner}/{coordinates.repo}"
    access_token = settings.github_token

    return GithubFileLoader(
        repo=repo_name,
        branch=branch,
        access_token=access_token,
        github_api_url=settings.github_api_base_url,
        file_filter=_repo_file_filter,
    )


def _repo_file_filter(path: str) -> bool:
    lower = path.lower()
    parts = {part for part in lower.split("/") if part}
    if parts.intersection(_IGNORED_PATH_PARTS):
        return False

    if lower.endswith("dockerfile"):
        return True

    return any(lower.endswith(ext) for ext in _ALLOWED_CODE_EXTENSIONS)


def _build_code_context(documents: list[Any], max_files: int, max_chars: int) -> str:
    snippets: list[str] = []
    total_chars = 0

    for document in documents:
        if len(snippets) >= max_files or total_chars >= max_chars:
            break

        text = (getattr(document, "page_content", "") or "").strip()
        if not text:
            continue

        metadata = getattr(document, "metadata", {}) or {}
        path = metadata.get("path") or metadata.get("source") or "unknown"

        trimmed = text[:4000]
        chunk = f"\n# File: {path}\n{trimmed}\n"
        if total_chars + len(chunk) > max_chars:
            remaining = max_chars - total_chars
            if remaining < 200:
                break
            chunk = chunk[:remaining]

        snippets.append(chunk)
        total_chars += len(chunk)

    return "\n".join(snippets)


def _build_stack_fallback(repo_payload: dict[str, Any]) -> list[str]:
    values: list[str] = []

    language = repo_payload.get("language")
    if isinstance(language, str) and language.strip():
        values.append(language.strip())

    topics = repo_payload.get("topics")
    if isinstance(topics, list):
        for topic in topics:
            if not isinstance(topic, str):
                continue
            normalized = " ".join(part.capitalize() for part in topic.split("-"))
            if normalized.strip():
                values.append(normalized.strip())

    seen: set[str] = set()
    deduplicated: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(value)

    return deduplicated


def _extract_last_page_link(link_header: str) -> str | None:
    if not link_header:
        return None

    for fragment in link_header.split(","):
        if 'rel="last"' not in fragment:
            continue
        match = re.search(r"<([^>]+)>", fragment)
        if match:
            return match.group(1)

    return None


def _parse_commit_datetime(commit_payload: dict[str, Any]) -> datetime | None:
    commit_block = commit_payload.get("commit")
    if not isinstance(commit_block, dict):
        return None

    author_block = commit_block.get("committer") or commit_block.get("author")
    if not isinstance(author_block, dict):
        return None

    raw_value = author_block.get("date")
    return _parse_github_datetime(raw_value)


def _parse_github_datetime(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_markdown_title(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[`*_#]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _build_github_api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
