import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes.applications import router as applications_router
from backend.app.api.routes.database import router as database_router
from backend.app.api.routes.extraction import router as extraction_router
from backend.app.core.config import settings
from backend.app.core.exceptions import ExtractionError
from backend.app.core.logging import get_logger, setup_logging
from backend.app.services.extraction_service import extraction_service

setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for setup and teardown."""
    logger.info("Initializing %s...", settings.APP_NAME)
    await extraction_service.initialize()
    yield
    logger.info("Shutting down %s...", settings.APP_NAME)
    await extraction_service.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Autonomous Bulk Job Website to Excel Extractor API",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Global Custom Exception Handler
@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    logger.error("Extraction error occurred: %s (Details: %s)", exc.message, exc.details)
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Register Routers
app.include_router(extraction_router)
app.include_router(database_router)
app.include_router(applications_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


if __name__ == "__main__":
    import uvicorn

    loop_type = "asyncio:ProactorEventLoop" if sys.platform == "win32" else "auto"

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=(settings.APP_ENV == "development"),
        reload_excludes=["backend/data/*", "downloads/*", "*.db", "*.db-wal", "*.db-shm"],
        loop=loop_type,
    )
