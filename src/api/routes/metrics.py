"""
Metrics overview and aggregate KPI routes.
Supports partitioned dataset views for FinTech Telemetry vs Kaggle CFPB Grievances.
"""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.anomaly import MetricsOverviewResponse
from src.database.session import get_db
from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent

router = APIRouter(prefix="/metrics", tags=["Metrics Overview"])


@router.get("/overview", response_model=MetricsOverviewResponse)
async def get_metrics_overview(
    dataset_source: str = Query("FINTECH_90D", description="Dataset partition to summarize (FINTECH_90D or KAGGLE_CFPB)"),
    db: AsyncSession = Depends(get_db),
) -> MetricsOverviewResponse:
    """
    Returns aggregate financial/grievance metrics and anomaly health counters for the selected dataset.
    """
    if dataset_source == "KAGGLE_CFPB":
        # 1. CFPB Ticket Aggregates
        total_tickets = await db.scalar(
            select(func.count(DisputeSupportTicket.id)).where(DisputeSupportTicket.dataset_source == "KAGGLE_CFPB")
        ) or 0

        disputed_tickets = await db.scalar(
            select(func.count(DisputeSupportTicket.id))
            .where(DisputeSupportTicket.dataset_source == "KAGGLE_CFPB")
            .where(DisputeSupportTicket.priority == "CRITICAL")
        ) or 0

        dispute_rate_pct = (disputed_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0
        avg_settlement_rate = max(100.0 - dispute_rate_pct, 0.0)

        # 2. CFPB Anomaly Counters
        total_anom = await db.scalar(
            select(func.count(AnomalyEvent.id)).where(AnomalyEvent.dataset_source == "KAGGLE_CFPB")
        ) or 0
        open_anom = await db.scalar(
            select(func.count(AnomalyEvent.id))
            .where(AnomalyEvent.dataset_source == "KAGGLE_CFPB")
            .where(AnomalyEvent.status == "OPEN")
        ) or 0
        critical_anom = await db.scalar(
            select(func.count(AnomalyEvent.id))
            .where(AnomalyEvent.dataset_source == "KAGGLE_CFPB")
            .where(AnomalyEvent.severity == "CRITICAL")
        ) or 0

        return MetricsOverviewResponse(
            total_spend_90d=round(float(total_tickets * 250.0), 2),  # Estimated disputed exposure volume
            total_transactions=int(total_tickets),
            avg_success_rate_pct=round(float(avg_settlement_rate), 2),
            total_anomalies_detected=int(total_anom),
            open_anomalies_count=int(open_anom),
            critical_anomalies_count=int(critical_anom),
        )

    # Default: FINTECH_90D
    metric_stmt = select(
        func.sum(DailySpendMetric.daily_spend_amount).label("total_spend"),
        func.sum(DailySpendMetric.transaction_count).label("total_tx"),
        func.avg(DailySpendMetric.success_rate_pct).label("avg_sr"),
    ).where(DailySpendMetric.dataset_source == "FINTECH_90D")
    
    metric_res = await db.execute(metric_stmt)
    total_spend, total_tx, avg_sr = metric_res.one()

    total_anom = await db.scalar(
        select(func.count(AnomalyEvent.id)).where(AnomalyEvent.dataset_source == "FINTECH_90D")
    ) or 0
    open_anom = await db.scalar(
        select(func.count(AnomalyEvent.id))
        .where(AnomalyEvent.dataset_source == "FINTECH_90D")
        .where(AnomalyEvent.status == "OPEN")
    ) or 0
    critical_anom = await db.scalar(
        select(func.count(AnomalyEvent.id))
        .where(AnomalyEvent.dataset_source == "FINTECH_90D")
        .where(AnomalyEvent.severity == "CRITICAL")
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
async def get_metrics_timeseries(
    dataset_source: str = Query("FINTECH_90D", description="Dataset partition for timeseries (FINTECH_90D or KAGGLE_CFPB)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns daily aggregated timeseries data for Chart.js visualization, scoped to active dataset.
    """
    stmt = (
        select(
            DailySpendMetric.metric_date,
            func.sum(DailySpendMetric.daily_spend_amount).label("daily_spend"),
            func.avg(DailySpendMetric.success_rate_pct).label("avg_success_rate"),
            func.sum(DailySpendMetric.transaction_count).label("tx_count"),
            func.avg(DailySpendMetric.chargeback_rate_pct).label("avg_dispute_rate"),
        )
        .where(DailySpendMetric.dataset_source == dataset_source)
        .group_by(DailySpendMetric.metric_date)
        .order_by(DailySpendMetric.metric_date.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return {
        "dataset_source": dataset_source,
        "dates": [row.metric_date.isoformat() for row in rows],
        "spend": [round(float(row.daily_spend), 2) for row in rows],
        "success_rate": [round(float(row.avg_success_rate), 2) for row in rows],
        "transactions": [int(row.tx_count) for row in rows],
        "dispute_rate": [round(float(row.avg_dispute_rate or 0.0), 2) for row in rows],
    }
