from fastapi import APIRouter
from src.api.routes.anomalies import router as anomalies_router
from src.api.routes.datasets import router as datasets_router
from src.api.routes.investigations import router as investigations_router
from src.api.routes.metrics import router as metrics_router

# Versioned API Router (/api/v1)
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(anomalies_router)
api_v1_router.include_router(investigations_router)
api_v1_router.include_router(datasets_router)

# Direct API Router (/api) for convenience
api_router = APIRouter(prefix="/api")
api_router.include_router(metrics_router)
api_router.include_router(anomalies_router)
api_router.include_router(investigations_router)
api_router.include_router(datasets_router)

__all__ = ["api_v1_router", "api_router", "datasets_router"]
