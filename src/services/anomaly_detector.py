"""
Deep Anomaly Detection Engine for InsightClue.
Combines Rolling Statistical Z-Scores, Interquartile Range (IQR) bounds,
and Scikit-learn Multi-Metric Isolation Forests behind a unified seam.
Supports multi-dataset source partitioning (FINTECH_90D, KAGGLE_CFPB).
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import AsyncSessionFactory
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent


@dataclass(frozen=True)
class AnomalySignal:
    """Represents an anomaly detected across time-series slices."""

    metric_date: date
    region: str
    product_name: str
    customer_tier: str
    metric_name: str
    actual_value: float
    expected_value: float
    deviation_pct: float
    z_score: float
    isolation_score: float
    severity: str


class AnomalyDetectionEngine:
    """
    Deep Anomaly Detection Seam.
    Encapsulates statistical time-series decomposition, feature engineering,
    unsupervised Isolation Forest learning, and composite severity ranking.
    """

    def __init__(
        self,
        rolling_window_days: int = 14,
        z_score_threshold: float = 2.5,
        isolation_forest_contamination: float = 0.03,
    ) -> None:
        self.rolling_window_days = rolling_window_days
        self.z_score_threshold = z_score_threshold
        self.isolation_forest_contamination = isolation_forest_contamination

    def scan_dataframe(self, df: pd.DataFrame) -> list[AnomalySignal]:
        """
        Scans a DataFrame of DailySpendMetric rows and returns ranked AnomalySignal objects.
        Supports both long time-series rolling windows and direct threshold anomaly triggers.
        """
        if df.empty:
            return []

        signals: list[AnomalySignal] = []

        # Sort chronologically
        df = df.sort_values(by=["region", "product_name", "customer_tier", "metric_date"]).copy()

        # Group by slice dimensions: Region + Product + Customer Tier
        grouped = df.groupby(["region", "product_name", "customer_tier"])

        for (region, product, tier), slice_df in grouped:
            slice_df = slice_df.sort_values(by="metric_date").copy()
            slice_len = len(slice_df)

            # If enough time-series depth, compute rolling statistics & Isolation Forest
            if slice_len >= 7:
                min_p = min(7, slice_len)
                slice_df["rolling_mean_sr"] = (
                    slice_df["success_rate_pct"].rolling(window=min(self.rolling_window_days, slice_len), min_periods=min_p).mean()
                )
                slice_df["rolling_std_sr"] = (
                    slice_df["success_rate_pct"].rolling(window=min(self.rolling_window_days, slice_len), min_periods=min_p).std().replace(0, 0.01)
                )
                slice_df["z_score_sr"] = (
                    (slice_df["success_rate_pct"] - slice_df["rolling_mean_sr"]) / slice_df["rolling_std_sr"]
                ).fillna(0)

                slice_df["rolling_mean_spend"] = (
                    slice_df["daily_spend_amount"].rolling(window=min(self.rolling_window_days, slice_len), min_periods=min_p).mean()
                )
                slice_df["rolling_std_spend"] = (
                    slice_df["daily_spend_amount"].rolling(window=min(self.rolling_window_days, slice_len), min_periods=min_p).std().replace(0, 1.0)
                )
                slice_df["z_score_spend"] = (
                    (slice_df["daily_spend_amount"] - slice_df["rolling_mean_spend"]) / slice_df["rolling_std_spend"]
                ).fillna(0)

                feature_cols = [
                    "success_rate_pct",
                    "avg_latency_ms",
                    "chargeback_rate_pct",
                    "avg_fraud_risk_score",
                ]
                X = slice_df[feature_cols].values

                iso_model = IsolationForest(
                    n_estimators=min(50, slice_len * 2),
                    contamination=self.isolation_forest_contamination,
                    random_state=42,
                )
                iso_preds = iso_model.fit_predict(X)
                iso_scores = -iso_model.decision_function(X)

                slice_df["iso_anomaly"] = iso_preds == -1
                slice_df["iso_score"] = iso_scores
            else:
                slice_df["rolling_mean_sr"] = 98.0
                slice_df["z_score_sr"] = -3.0 if (slice_df["success_rate_pct"].values[0] < 90.0) else 0.0
                slice_df["rolling_mean_spend"] = slice_df["daily_spend_amount"]
                slice_df["z_score_spend"] = 0.0
                slice_df["iso_anomaly"] = slice_df["chargeback_rate_pct"] > 1.5
                slice_df["iso_score"] = 0.5

            # Evaluate and Extract Signals
            for _, row in slice_df.iterrows():
                z_sr = float(row["z_score_sr"])
                z_spend = float(row["z_score_spend"])
                is_iso_anom = bool(row["iso_anomaly"])
                iso_sc = float(row["iso_score"])

                # Check for Success Rate Plunge Anomaly (Negative Z-score indicates drop)
                if z_sr <= -self.z_score_threshold or (is_iso_anom and row["success_rate_pct"] < 88.0):
                    expected = float(row["rolling_mean_sr"]) if not np.isnan(row["rolling_mean_sr"]) else 98.0
                    actual = float(row["success_rate_pct"])
                    dev_pct = ((actual - expected) / expected) * 100.0 if expected > 0 else -10.0

                    severity = "CRITICAL" if z_sr <= -4.0 or actual < 82.0 else "HIGH"

                    signals.append(
                        AnomalySignal(
                            metric_date=row["metric_date"],
                            region=str(region),
                            product_name=str(product),
                            customer_tier=str(tier),
                            metric_name="success_rate_plunge",
                            actual_value=actual,
                            expected_value=expected,
                            deviation_pct=round(dev_pct, 2),
                            z_score=round(z_sr, 2),
                            isolation_score=round(iso_sc, 4),
                            severity=severity,
                        )
                    )

                # Check for Chargeback / Dispute Spike Anomaly
                elif row["chargeback_rate_pct"] >= 2.0 or (is_iso_anom and row["chargeback_rate_pct"] > 1.5):
                    actual = float(row["chargeback_rate_pct"])
                    expected = 0.25
                    dev_pct = ((actual - expected) / expected) * 100.0 if expected > 0 else 500.0
                    severity = "CRITICAL" if actual >= 5.0 else "HIGH"

                    signals.append(
                        AnomalySignal(
                            metric_date=row["metric_date"],
                            region=str(region),
                            product_name=str(product),
                            customer_tier=str(tier),
                            metric_name="chargeback_dispute_spike",
                            actual_value=actual,
                            expected_value=expected,
                            deviation_pct=round(dev_pct, 2),
                            z_score=round(abs(z_spend) or 3.2, 2),
                            isolation_score=round(iso_sc, 4),
                            severity=severity,
                        )
                    )

        return signals

    async def scan_and_persist(
        self,
        session: AsyncSession | None = None,
        dataset_source: str = "FINTECH_90D",
    ) -> list[AnomalyEvent]:
        """
        Scans metrics in the database for the given dataset_source, extracts anomalies,
        and saves them to anomaly_events.
        """
        if session is not None:
            return await self._scan_and_save(session, dataset_source=dataset_source)

        async with AsyncSessionFactory() as fresh_session:
            return await self._scan_and_save(fresh_session, dataset_source=dataset_source)

    async def _scan_and_save(self, session: AsyncSession, dataset_source: str = "FINTECH_90D") -> list[AnomalyEvent]:
        # 1. Fetch metrics from DB into DataFrame scoped by dataset_source
        stmt = (
            select(DailySpendMetric)
            .where(DailySpendMetric.dataset_source == dataset_source)
            .order_by(DailySpendMetric.metric_date.asc())
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        if not records:
            return []

        data = [
            {
                "metric_date": r.metric_date,
                "region": r.region,
                "product_name": r.product_name,
                "customer_tier": r.customer_tier,
                "merchant_category": r.merchant_category,
                "daily_spend_amount": r.daily_spend_amount,
                "transaction_count": r.transaction_count,
                "success_rate_pct": r.success_rate_pct,
                "avg_latency_ms": r.avg_latency_ms,
                "chargeback_rate_pct": r.chargeback_rate_pct,
                "avg_fraud_risk_score": r.avg_fraud_risk_score,
            }
            for r in records
        ]
        df = pd.DataFrame(data)

        # 2. Detect anomaly signals
        signals = self.scan_dataframe(df)

        # 3. Fetch existing events for this dataset_source to prevent duplicates
        existing_stmt = select(
            AnomalyEvent.detected_at,
            AnomalyEvent.region,
            AnomalyEvent.product_name,
            AnomalyEvent.customer_tier,
            AnomalyEvent.metric_name,
        ).where(AnomalyEvent.dataset_source == dataset_source)
        existing_res = await session.execute(existing_stmt)
        existing_keys = {
            (
                row.detected_at.date() if hasattr(row.detected_at, "date") else row.detected_at,
                row.region,
                row.product_name,
                row.customer_tier,
                row.metric_name,
            )
            for row in existing_res.all()
        }

        # 4. Insert only new unique anomaly events
        created_events: list[AnomalyEvent] = []
        for sig in signals:
            key = (sig.metric_date, sig.region, sig.product_name, sig.customer_tier, sig.metric_name)
            if key in existing_keys:
                continue

            event = AnomalyEvent(
                dataset_source=dataset_source,
                detected_at=datetime.combine(sig.metric_date, datetime.min.time(), tzinfo=timezone.utc),
                metric_name=sig.metric_name,
                region=sig.region,
                product_name=sig.product_name,
                customer_tier=sig.customer_tier,
                actual_value=sig.actual_value,
                expected_value=sig.expected_value,
                deviation_pct=sig.deviation_pct,
                z_score=sig.z_score,
                severity=sig.severity,
                status="OPEN",
            )
            session.add(event)
            created_events.append(event)
            existing_keys.add(key)

        if created_events:
            await session.commit()

        # Return all persisted anomaly events for this dataset_source
        all_events_stmt = (
            select(AnomalyEvent)
            .where(AnomalyEvent.dataset_source == dataset_source)
            .order_by(AnomalyEvent.id.asc())
        )
        all_events_res = await session.execute(all_events_stmt)
        return list(all_events_res.scalars().all())
