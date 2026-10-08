"""
Deep Telemetry Metric Store & Aggregation Seam.
Encapsulates all SQL aggregations, date groupings, zero-division guards,
and multi-table KPI synthesis behind a unified, high-leverage interface.
"""

from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.anomaly import MetricsOverviewResponse
from src.database.session import AsyncSessionFactory
from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent


class TelemetryMetricStore:
    """
    Deep module interface for telemetry metrics, aggregation windows, and dataset partition discovery.
    """

    async def list_datasets(self, session: AsyncSession | None = None) -> list[str]:
        """
        Returns distinct dataset partition sources present in the database.
        """
        async def _query(sess: AsyncSession) -> list[str]:
            metric_sources = (await sess.scalars(select(DailySpendMetric.dataset_source).distinct())).all()
            ticket_sources = (await sess.scalars(select(DisputeSupportTicket.dataset_source).distinct())).all()
            sources = sorted(list(set(metric_sources) | set(ticket_sources)))
            return sources if sources else ["KAGGLE_CFPB"]

        if session is not None:
            return await _query(session)

        async with AsyncSessionFactory() as fresh_session:
            return await _query(fresh_session)

    async def get_overview(
        self,
        dataset_source: str = "KAGGLE_CFPB",
        session: AsyncSession | None = None,
    ) -> MetricsOverviewResponse:
        """
        Computes aggregate financial/grievance metrics and anomaly health counters for the selected dataset.
        """
        async def _calculate(sess: AsyncSession) -> MetricsOverviewResponse:
            # 1. Aggregate from daily_spend_metrics
            metric_stmt = select(
                func.sum(DailySpendMetric.daily_spend_amount).label("total_spend"),
                func.sum(DailySpendMetric.transaction_count).label("total_tx"),
                func.avg(DailySpendMetric.success_rate_pct).label("avg_sr"),
            ).where(DailySpendMetric.dataset_source == dataset_source)

            metric_res = await sess.execute(metric_stmt)
            total_spend, total_tx, avg_sr = metric_res.one()

            # 2. Fallback to dispute_support_tickets if no metrics rows
            if total_tx is None or total_tx == 0:
                total_tickets = await sess.scalar(
                    select(func.count(DisputeSupportTicket.id)).where(DisputeSupportTicket.dataset_source == dataset_source)
                ) or 0

                disputed_tickets = await sess.scalar(
                    select(func.count(DisputeSupportTicket.id))
                    .where(DisputeSupportTicket.dataset_source == dataset_source)
                    .where(DisputeSupportTicket.priority == "CRITICAL")
                ) or 0

                dispute_rate_pct = (disputed_tickets / total_tickets * 100.0) if total_tickets > 0 else 0.0
                avg_sr = max(100.0 - dispute_rate_pct, 0.0)
                total_tx = total_tickets
                total_spend = total_tickets * 250.0

            # 3. Anomaly Counters
            total_anom = await sess.scalar(
                select(func.count(AnomalyEvent.id)).where(AnomalyEvent.dataset_source == dataset_source)
            ) or 0
            open_anom = await sess.scalar(
                select(func.count(AnomalyEvent.id))
                .where(AnomalyEvent.dataset_source == dataset_source)
                .where(AnomalyEvent.status == "OPEN")
            ) or 0
            critical_anom = await sess.scalar(
                select(func.count(AnomalyEvent.id))
                .where(AnomalyEvent.dataset_source == dataset_source)
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

        if session is not None:
            return await _calculate(session)

        async with AsyncSessionFactory() as fresh_session:
            return await _calculate(fresh_session)

    async def get_timeseries(
        self,
        dataset_source: str = "KAGGLE_CFPB",
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """
        Returns daily aggregated timeseries data for Chart.js visualization, scoped to active dataset.
        """
        async def _fetch(sess: AsyncSession) -> dict[str, Any]:
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
            result = await sess.execute(stmt)
            rows = result.all()

            return {
                "dataset_source": dataset_source,
                "dates": [row.metric_date.isoformat() for row in rows],
                "spend": [round(float(row.daily_spend or 0.0), 2) for row in rows],
                "success_rate": [round(float(row.avg_success_rate or 0.0), 2) for row in rows],
                "transactions": [int(row.tx_count or 0) for row in rows],
                "dispute_rate": [round(float(row.avg_dispute_rate or 0.0), 2) for row in rows],
            }

        if session is not None:
            return await _fetch(session)

        async with AsyncSessionFactory() as fresh_session:
            return await _fetch(fresh_session)
