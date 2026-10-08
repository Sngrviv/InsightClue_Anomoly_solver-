"""
Deep Telemetry Metric Store & Aggregation Seam.
Encapsulates all SQL aggregations, date groupings, zero-division guards,
and multi-table KPI synthesis behind a unified, high-leverage interface.
"""

import asyncio
import re
from typing import Any
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.anomaly import MetricsOverviewResponse
from src.database.session import AsyncSessionFactory
from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent


class SQLSecurityViolation(Exception):
    """Raised when an agent attempts an unsafe or non-SELECT SQL operation."""
    pass


class TelemetryMetricStore:
    """
    Deep module interface for telemetry metrics, aggregation windows, dataset partition discovery,
    and safe sandboxed analytical SQL execution.
    """

    FORBIDDEN_KEYWORDS = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bCREATE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bCALL\b",
        r"\bMERGE\b",
    ]

    def __init__(self, max_rows: int = 50, timeout_seconds: float = 5.0) -> None:
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self._cached_schema: str | None = None

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

    async def get_schema_summary(self, session: AsyncSession | None = None) -> str:
        """
        Dynamically introspects PostgreSQL table schemas and returns a formatted description for LLM agents.
        """
        if self._cached_schema:
            return self._cached_schema

        query = text("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('daily_spend_metrics', 'dispute_support_tickets', 'payment_gateway_logs', 'anomaly_events')
            ORDER BY table_name, ordinal_position;
        """)

        async def _fetch(sess: AsyncSession) -> str:
            res = await sess.execute(query)
            rows = res.all()
            if not rows:
                return (
                    "TABLES:\n"
                    "- daily_spend_metrics (dataset_source, metric_date, region, product_name, customer_tier, daily_spend_amount, transaction_count, success_rate_pct, avg_latency_ms, chargeback_rate_pct)\n"
                    "- dispute_support_tickets (dataset_source, ticket_created_at, region, product_name, customer_tier, issue_category, priority, subject, message)\n"
                    "- anomaly_events (dataset_source, detected_at, region, product_name, customer_tier, metric_name, actual_value, expected_value, severity, status)"
                )
            
            tables: dict[str, list[str]] = {}
            for t_name, c_name, d_type in rows:
                if t_name not in tables:
                    tables[t_name] = []
                tables[t_name].append(f"{c_name} {d_type}")

            summary_lines = ["ACTIVE DATABASE SCHEMAS:"]
            for t_name, cols in tables.items():
                summary_lines.append(f"- {t_name} ({', '.join(cols)})")
            
            return "\n".join(summary_lines)

        if session is not None:
            schema_str = await _fetch(session)
        else:
            async with AsyncSessionFactory() as fresh_session:
                schema_str = await _fetch(fresh_session)

        self._cached_schema = schema_str
        return schema_str

    def validate_query(self, query: str) -> str:
        """
        Validates that the SQL query is strictly a read-only SELECT or WITH statement.
        Returns the sanitized query with a forced LIMIT clause.
        """
        clean_query = query.strip()

        if clean_query.endswith(";"):
            clean_query = clean_query[:-1].strip()

        if ";" in clean_query:
            raise SQLSecurityViolation("Multiple SQL statements in a single query are forbidden.")

        for pattern in self.FORBIDDEN_KEYWORDS:
            if re.search(pattern, clean_query, re.IGNORECASE):
                keyword = pattern.replace(r"\b", "")
                raise SQLSecurityViolation(
                    f"Forbidden keyword '{keyword}' detected. SQL Sandbox is strictly READ-ONLY."
                )

        if not (
            re.match(r"^SELECT\b", clean_query, re.IGNORECASE)
            or re.match(r"^WITH\b", clean_query, re.IGNORECASE)
        ):
            raise SQLSecurityViolation("Query must start with SELECT or WITH.")

        if not re.search(r"\bLIMIT\s+\d+\b", clean_query, re.IGNORECASE):
            clean_query = f"{clean_query} LIMIT {self.max_rows}"

        return clean_query

    def _serialize_value(self, val: Any) -> Any:
        """Converts database objects (date, datetime, Decimal, UUID) into JSON-serializable primitives."""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        elif hasattr(val, "__float__"):
            return float(val)
        elif hasattr(val, "__str__") and not isinstance(val, (int, float, bool, list, dict, type(None))):
            return str(val)
        return val

    async def execute_sandboxed_query(
        self,
        query: str,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """
        Safely executes the validated read-only query against PostgreSQL and returns results as dicts.
        """
        validated_sql = self.validate_query(query)

        async def _run(sess: AsyncSession) -> list[dict[str, Any]]:
            await sess.execute(text("SET TRANSACTION READ ONLY"))
            result = await sess.execute(text(validated_sql))
            rows = result.mappings().all()
            return [
                {k: self._serialize_value(v) for k, v in row.items()}
                for row in rows
            ]

        if session is not None:
            return await asyncio.wait_for(_run(session), timeout=self.timeout_seconds)

        async with AsyncSessionFactory() as fresh_session:
            return await asyncio.wait_for(_run(fresh_session), timeout=self.timeout_seconds)

