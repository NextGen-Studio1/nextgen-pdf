from fastapi import APIRouter
from app.api.v1.endpoints import health, jobs, pdf, dashboard

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(jobs.router, tags=["Jobs & Files"])
api_router.include_router(pdf.router, tags=["PDF Processing"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
