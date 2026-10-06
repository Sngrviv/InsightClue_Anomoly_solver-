"""
FastAPI Main Application for InsightClue AI Data Detective.
Provides REST and Server-Sent Events (SSE) interfaces for telemetry metrics,
anomaly detection triggers, and autonomous multi-agent RCA investigations.
"""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.api.routes import api_v1_router
import asyncio
from typing import Any
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.config.settings import get_settings
from src.database.session import AsyncSessionFactory, close_db_engine, init_db_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Initializes database engines on startup and gracefully closes connections on shutdown.
    """
    logger.info("Initializing InsightClue database engines...")
    init_db_engine()
    yield
    logger.info("Closing InsightClue database engines...")
    await close_db_engine()


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Autonomous FinTech Anomaly Detection and Multi-Agent Root Cause Analysis (RCA) Engine.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Global Exception Handler for Database / Docker Container Offline Errors
@app.exception_handler(OperationalError)
@app.exception_handler(ConnectionRefusedError)
@app.exception_handler(OSError)
async def db_connection_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Interceptors database offline / container down errors and serves user-friendly 503 guidance."""
    err_str = str(exc)
    logger.warning(f"Intercepted database connection failure on {request.url.path}: {err_str}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "DATABASE_SERVICE_OFFLINE",
            "detail": "Database engine is offline. PostgreSQL / pgvector container is unreachable on port 5432.",
            "action_required": "Please ensure Docker Desktop is running and run 'docker-compose up -d' in your terminal.",
            "retry_endpoint": "/api/v1/health",
        },
    )

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(api_v1_router)

# Mount Static Dashboard Files
static_path = Path(__file__).resolve().parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/", include_in_schema=False)
async def serve_dashboard() -> FileResponse:
    """Serves the Single-Page FinTech Mission Control Dashboard."""
    index_file = static_path / "index.html"
    return FileResponse(str(index_file))


async def probe_database_connection() -> tuple[bool, str | None]:
    """Probes PostgreSQL database connectivity with a strict timeout."""
    try:
        async with asyncio.timeout(2.0):
            async with AsyncSessionFactory() as session:
                await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """
    Active system and database health check endpoint.
    Probes PostgreSQL & pgvector container readiness.
    """
    is_db_up, db_err = await probe_database_connection()
    return {
        "status": "healthy" if is_db_up else "degraded",
        "database": {
            "connected": is_db_up,
            "engine": "PostgreSQL 16 + pgvector (localhost:5432)",
            "error": db_err if not is_db_up else None,
            "action_required": (
                "Ensure Docker Desktop is running and execute 'docker-compose up -d'."
                if not is_db_up
                else None
            ),
        },
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
