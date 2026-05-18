from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.portfolios import router as public_portfolios_router
from app.api.v1.endpoints.educations import router as educations_router
from app.api.v1.endpoints.profile import router as profile_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.publications import router as portfolio_publications_router
from app.api.v1.endpoints.resumes import router as resumes_router
from app.api.v1.endpoints.companies import router as companies_router
from app.api.v1.endpoints.jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(educations_router)
api_router.include_router(projects_router)
api_router.include_router(resumes_router)
api_router.include_router(portfolio_publications_router)
api_router.include_router(public_portfolios_router)
api_router.include_router(companies_router)
api_router.include_router(jobs_router)
