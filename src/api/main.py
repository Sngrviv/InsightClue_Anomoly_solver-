"""
FastAPI Main Application for InsightClue AI Data Detective.
Provides REST and Server-Sent Events (SSE) interfaces for telemetry metrics,
anomaly detection triggers, and autonomous multi-agent RCA investigations.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import api_v1_router
from src.config.settings import get_settings
from src.database.session import close_db_engine, init_db_engine

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


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """
    System health check endpoint.
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
