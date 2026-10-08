"""
Metrics overview and aggregate KPI routes.
Powered by the deep TelemetryMetricStore seam.
"""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.anomaly import MetricsOverviewResponse
from src.database.session import get_db
from src.services.telemetry_store import TelemetryMetricStore

router = APIRouter(prefix="/metrics", tags=["Metrics Overview"])
_telemetry_store = TelemetryMetricStore()


@router.get("/datasets")
async def list_available_datasets(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """
    Returns distinct dataset partition sources present in the database.
    """
    return await _telemetry_store.list_datasets(session=db)


@router.get("/overview", response_model=MetricsOverviewResponse)
async def get_metrics_overview(
    dataset_source: str = Query("KAGGLE_CFPB", description="Dataset partition to summarize"),
    db: AsyncSession = Depends(get_db),
) -> MetricsOverviewResponse:
    """
    Returns aggregate financial/grievance metrics and anomaly health counters for the selected dataset.
    """
    return await _telemetry_store.get_overview(dataset_source=dataset_source, session=db)


@router.get("/timeseries")
async def get_metrics_timeseries(
    dataset_source: str = Query("KAGGLE_CFPB", description="Dataset partition for timeseries"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns daily aggregated timeseries data for Chart.js visualization, scoped to active dataset.
    """
    return await _telemetry_store.get_timeseries(dataset_source=dataset_source, session=db)
