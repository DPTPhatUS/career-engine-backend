from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services import codexpert_agent as codexpert_agent_service
from app.services.github_loader import RepoSnapshot, fetch_repo_snapshot, parse_github_repo_url

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
    agent = codexpert_agent or codexpert_agent_service.build_codexpert_agent(settings)
    question = _build_autofill_question(snapshot)
    raw_text = await codexpert_agent_service.query_codexpert(agent, snapshot, question, "project_autofill")
    fallback_title = codexpert_agent_service.fallback_project_title(snapshot.coordinates.repo)
    title, tech_stack, bullets = codexpert_agent_service.normalize_project_generation_output(
        raw_text,
        fallback_title=fallback_title,
        fallback_stack=[],
    )
    return title, tech_stack, bullets


def _build_autofill_question(snapshot: RepoSnapshot) -> str:
    return (
        f"{_AUTOFILL_QUESTION}\n\n"
        "Repository:\n"
        f"- URL: {snapshot.html_url}\n"
        f"- Owner: {snapshot.coordinates.owner}\n"
        f"- Name: {snapshot.coordinates.repo}\n"
        f"- Default branch: {snapshot.default_branch}\n"
    )
