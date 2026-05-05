from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.educations import router as educations_router
from app.api.v1.endpoints.profile import router as profile_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.resumes import router as resumes_router
from app.api.v1.endpoints.target_companies import router as target_companies_router
from app.api.v1.endpoints.target_jobs import router as target_jobs_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(educations_router)
api_router.include_router(projects_router)
api_router.include_router(resumes_router)
api_router.include_router(target_companies_router)
api_router.include_router(target_jobs_router)
