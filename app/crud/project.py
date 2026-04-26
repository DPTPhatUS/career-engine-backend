from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import Project


async def list_projects_by_user_id(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.scalars(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.sort_order.asc(), Project.created_at.asc())
    )
    return list(result)


async def get_project_by_id(db: AsyncSession, user_id: str, project_id: str) -> Project | None:
    return await db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))


async def list_projects_by_ids(db: AsyncSession, user_id: str, project_ids: list[str]) -> list[Project]:
    if not project_ids:
        return []

    result = await db.scalars(
        select(Project).where(Project.user_id == user_id, Project.id.in_(project_ids))
    )
    projects = list(result)
    project_by_id = {project.id: project for project in projects}

    return [project_by_id[project_id] for project_id in project_ids if project_id in project_by_id]


async def create_project(db: AsyncSession, user_id: str, data: dict, sort_order: int | None) -> Project:
    next_sort_order = sort_order
    if next_sort_order is None:
        max_sort = await db.scalar(select(func.max(Project.sort_order)).where(Project.user_id == user_id))
        next_sort_order = 0 if max_sort is None else max_sort + 1

    project = Project(user_id=user_id, sort_order=next_sort_order, **data)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(db: AsyncSession, project: Project, data: dict) -> Project:
    for field, value in data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.commit()