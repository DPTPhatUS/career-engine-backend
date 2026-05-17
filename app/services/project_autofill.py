from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services import codexpert_agent as codexpert_agent_service
from app.services.github_loader import RepoMetadata, fetch_repo_metadata, parse_github_repo_url

_AUTOFILL_QUESTION = """
Analyze this repository and generate resume-ready project description.
Return only valid JSON with this exact shape:
{
  "title": "short project title",
  "tech_stack": "comma-separated technologies",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}
Rules:
- Use repository evidence from code, docs, package files, and configuration.
- Keep tech_stack concise and deduplicated.
- Produce exactly 3 accomplishment bullets.
- Bullets must be impact-oriented and written in past tense.
- Do not include markdown, citations, or extra keys.
""".strip()


async def autofill_project_from_github(github_url: str, settings: Settings) -> dict[str, Any]:
    coordinates = parse_github_repo_url(github_url)
    repo_metadata = await fetch_repo_metadata(coordinates, settings)
    title, tech_stack, bullets = await generate_project_summary(repo_metadata, settings)

    return {
        "title": title,
        "date_range": repo_metadata.date_range,
        "github_url": repo_metadata.html_url,
        "tech_stack": tech_stack,
        "bullets": bullets,
    }


async def generate_project_summary(
    repo_metadata: RepoMetadata,
    settings: Settings,
    codexpert_agent: Any | None = None,
) -> tuple[str, str, list[str]]:
    agent = codexpert_agent or codexpert_agent_service.build_codexpert_agent(settings)
    raw_text = await codexpert_agent_service.query_codexpert(
        agent,
        repo_metadata,
        _AUTOFILL_QUESTION,
        "project_autofill",
    )
    title, tech_stack, bullets = codexpert_agent_service.parse_project_generation_output(raw_text)
    return title, tech_stack, bullets
