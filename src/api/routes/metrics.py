"""
Metrics overview and aggregate KPI routes.
"""

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.anomaly import MetricsOverviewResponse
from src.database.session import get_db
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent

router = APIRouter(prefix="/metrics", tags=["Metrics Overview"])


@router.get("/overview", response_model=MetricsOverviewResponse)
async def get_metrics_overview(db: AsyncSession = Depends(get_db)) -> MetricsOverviewResponse:
    """
    Returns high-level aggregate financial metrics and anomaly health counters.
    """
    # 1. Aggregate FinTech KPIs
    metric_stmt = select(
        func.sum(DailySpendMetric.daily_spend_amount).label("total_spend"),
        func.sum(DailySpendMetric.transaction_count).label("total_tx"),
        func.avg(DailySpendMetric.success_rate_pct).label("avg_sr"),
    )
    metric_res = await db.execute(metric_stmt)
    total_spend, total_tx, avg_sr = metric_res.one()

    # 2. Anomaly Counters
    total_anom = await db.scalar(select(func.count(AnomalyEvent.id))) or 0
    open_anom = await db.scalar(
        select(func.count(AnomalyEvent.id)).where(AnomalyEvent.status == "OPEN")
    ) or 0
    critical_anom = await db.scalar(
        select(func.count(AnomalyEvent.id)).where(AnomalyEvent.severity == "CRITICAL")
    ) or 0

    return MetricsOverviewResponse(
        total_spend_90d=round(float(total_spend or 0.0), 2),
        total_transactions=int(total_tx or 0),
        avg_success_rate_pct=round(float(avg_sr or 0.0), 2),
        total_anomalies_detected=int(total_anom),
        open_anomalies_count=int(open_anom),
        critical_anomalies_count=int(critical_anom),
    )


@router.get("/timeseries")
async def get_metrics_timeseries(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Returns daily aggregated timeseries data for Chart.js visualization.
    """
    stmt = (
        select(
            DailySpendMetric.metric_date,
            func.sum(DailySpendMetric.daily_spend_amount).label("daily_spend"),
            func.avg(DailySpendMetric.success_rate_pct).label("avg_success_rate"),
            func.sum(DailySpendMetric.transaction_count).label("tx_count"),
        )
        .group_by(DailySpendMetric.metric_date)
        .order_by(DailySpendMetric.metric_date.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return {
        "dates": [row.metric_date.isoformat() for row in rows],
        "spend": [round(float(row.daily_spend), 2) for row in rows],
        "success_rate": [round(float(row.avg_success_rate), 2) for row in rows],
        "transactions": [int(row.tx_count) for row in rows],
    }
