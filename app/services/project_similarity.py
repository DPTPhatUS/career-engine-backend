from __future__ import annotations

import asyncio
import hashlib
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.embedding import (
    get_job_embedding_by_job_id_and_model,
    get_project_embedding_by_project_id_and_model,
    upsert_job_embedding,
    upsert_project_embedding,
)

_EMBEDDING_MODELS: dict[str, Any] = {}


async def rank_projects_for_job(
    *,
    db: AsyncSession,
    user_id: str,
    job: Any,
    projects: list[Any],
    settings: Settings,
) -> list[dict[str, int | str]]:
    if not projects:
        return []

    embedding_model = settings.project_similarity_embedding_model
    floor = settings.project_similarity_score_floor
    ceiling = settings.project_similarity_score_ceiling

    job_text = _build_job_text(job)
    job_hash = _sha256_text(job_text)
    cached_job = await get_job_embedding_by_job_id_and_model(db, user_id, job.id, embedding_model)
    if cached_job and cached_job.content_hash == job_hash:
        job_embedding = _coerce_embedding(cached_job.embedding)
    else:
        job_embedding = await _generate_embedding(embedding_model, job_text)
        await upsert_job_embedding(
            db=db,
            user_id=user_id,
            job_id=job.id,
            embedding_model=embedding_model,
            content_hash=job_hash,
            embedding=job_embedding,
        )

    scored_items: list[dict[str, Any]] = []
    for project in projects:
        project_text = _build_project_text(project)
        project_hash = _sha256_text(project_text)
        cached_project = await get_project_embedding_by_project_id_and_model(
            db, user_id, project.id, embedding_model
        )
        if cached_project and cached_project.content_hash == project_hash:
            project_embedding = _coerce_embedding(cached_project.embedding)
        else:
            project_embedding = await _generate_embedding(embedding_model, project_text)
            await upsert_project_embedding(
                db=db,
                user_id=user_id,
                project_id=project.id,
                embedding_model=embedding_model,
                content_hash=project_hash,
                embedding=project_embedding,
            )

        cosine_score = _cosine_similarity(job_embedding, project_embedding)
        display_score = _to_display_score(cosine_score, floor, ceiling)
        scored_items.append(
            {
                "project_id": project.id,
                "similarity_score": display_score,
                "sort_order": project.sort_order,
                "created_at": project.created_at,
            }
        )

    scored_items.sort(
        key=lambda item: (
            -item["similarity_score"],
            item["sort_order"],
            item["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
        )
    )

    return [
        {"project_id": item["project_id"], "similarity_score": item["similarity_score"]}
        for item in scored_items
    ]


def _build_job_text(job: Any) -> str:
    return _canonical_text([job.title, job.job_description, job.job_requirements])


def _build_project_text(project: Any) -> str:
    bullets = project.bullets or []
    return _canonical_text([project.title, project.tech_stack or "", *bullets])


def _canonical_text(parts: list[str]) -> str:
    normalized = []
    for part in parts:
        cleaned = (part or "").strip()
        if cleaned:
            normalized.append(cleaned)
    return "\n".join(normalized)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _generate_embedding(model_name: str, text: str) -> list[float]:
    model = await asyncio.to_thread(_get_sentence_transformer, model_name)
    embedding = await asyncio.to_thread(model.encode, text)
    return _coerce_embedding(embedding)


def _get_sentence_transformer(model_name: str) -> Any:
    if model_name in _EMBEDDING_MODELS:
        return _EMBEDDING_MODELS[model_name]

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    _EMBEDDING_MODELS[model_name] = model
    return model


def _coerce_embedding(raw: Any) -> list[float]:
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    return [float(value) for value in raw]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(left * right for left, right in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _to_display_score(cosine_score: float, floor: float, ceiling: float) -> int:
    if ceiling <= floor:
        return 0
    scaled = (cosine_score - floor) / (ceiling - floor) * 100
    return round(min(100.0, max(0.0, scaled)))
