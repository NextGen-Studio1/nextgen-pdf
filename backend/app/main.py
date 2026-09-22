import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import NextGenException, nextgen_exception_handler
from app.core.logging import logger
from app.db.database import engine, Base
from app.api.v1.router import api_router
from app.services.cleanup_service import CleanupService

# Initialize database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Exception Handlers
app.add_exception_handler(NextGenException, nextgen_exception_handler)

# API Router Registration
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
    # Spawn background cleanup worker loop
    asyncio.create_task(CleanupService.start_periodic_cleanup(interval_seconds=1800))

@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} v{settings.VERSION}",
        "docs": "/docs",
        "api_v1": settings.API_V1_STR
    }
