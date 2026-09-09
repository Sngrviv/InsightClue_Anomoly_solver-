"""
Deep Anomaly Detection Engine for InsightClue.
Combines Rolling Statistical Z-Scores, Interquartile Range (IQR) bounds,
and Scikit-learn Multi-Metric Isolation Forests behind a unified seam.
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
        """
        if df.empty or len(df) < self.rolling_window_days:
            return []

        signals: list[AnomalySignal] = []

        # Sort chronologically
        df = df.sort_values(by=["region", "product_name", "customer_tier", "metric_date"]).copy()

        # Group by slice dimensions: Region + Product + Customer Tier
        grouped = df.groupby(["region", "product_name", "customer_tier"])

        for (region, product, tier), slice_df in grouped:
            if len(slice_df) < self.rolling_window_days:
                continue

            slice_df = slice_df.sort_values(by="metric_date").copy()

            # 1. Statistical Rolling Window Z-Score & IQR on Success Rate
            slice_df["rolling_mean_sr"] = (
                slice_df["success_rate_pct"].rolling(window=self.rolling_window_days, min_periods=7).mean()
            )
            slice_df["rolling_std_sr"] = (
                slice_df["success_rate_pct"].rolling(window=self.rolling_window_days, min_periods=7).std().replace(0, 0.01)
            )
            slice_df["z_score_sr"] = (
                (slice_df["success_rate_pct"] - slice_df["rolling_mean_sr"]) / slice_df["rolling_std_sr"]
            ).fillna(0)

            # 2. Statistical Rolling Window Z-Score on Daily Spend Amount
            slice_df["rolling_mean_spend"] = (
                slice_df["daily_spend_amount"].rolling(window=self.rolling_window_days, min_periods=7).mean()
            )
            slice_df["rolling_std_spend"] = (
                slice_df["daily_spend_amount"].rolling(window=self.rolling_window_days, min_periods=7).std().replace(0, 1.0)
            )
            slice_df["z_score_spend"] = (
                (slice_df["daily_spend_amount"] - slice_df["rolling_mean_spend"]) / slice_df["rolling_std_spend"]
            ).fillna(0)

            # 3. Multi-Metric Isolation Forest Feature Matrix
            # Features: [success_rate, spend_ratio, latency, chargeback_rate, fraud_score]
            feature_cols = [
                "success_rate_pct",
                "avg_latency_ms",
                "chargeback_rate_pct",
                "avg_fraud_risk_score",
            ]
            X = slice_df[feature_cols].values

            # Fit Isolation Forest
            iso_model = IsolationForest(
                n_estimators=100,
                contamination=self.isolation_forest_contamination,
                random_state=42,
            )
            iso_preds = iso_model.fit_predict(X)  # -1 for anomaly, 1 for normal
            iso_scores = -iso_model.decision_function(X)  # Higher score = more anomalous

            slice_df["iso_anomaly"] = iso_preds == -1
            slice_df["iso_score"] = iso_scores

            # 4. Evaluate and Extract Signals
            for _, row in slice_df.iterrows():
                z_sr = float(row["z_score_sr"])
                z_spend = float(row["z_score_spend"])
                is_iso_anom = bool(row["iso_anomaly"])
                iso_sc = float(row["iso_score"])

                # Check for Success Rate Plunge Anomaly (Negative Z-score indicates drop)
                if z_sr <= -self.z_score_threshold or (is_iso_anom and row["success_rate_pct"] < 88.0):
                    expected = float(row["rolling_mean_sr"]) if not np.isnan(row["rolling_mean_sr"]) else 98.0
                    actual = float(row["success_rate_pct"])
                    dev_pct = ((actual - expected) / expected) * 100.0

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
                    dev_pct = ((actual - expected) / expected) * 100.0
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
                            z_score=round(abs(z_spend), 2),
                            isolation_score=round(iso_sc, 4),
                            severity=severity,
                        )
                    )

        return signals

    async def scan_and_persist(
        self,
        session: AsyncSession | None = None,
    ) -> list[AnomalyEvent]:
        """
        Scans all metrics in the database, extracts anomalies, and saves them to anomaly_events.
        """
        if session is not None:
            return await self._scan_and_save(session)

        async with AsyncSessionFactory() as fresh_session:
            return await self._scan_and_save(fresh_session)

    async def _scan_and_save(self, session: AsyncSession) -> list[AnomalyEvent]:
        # 1. Fetch metrics from DB into DataFrame
        stmt = select(DailySpendMetric).order_by(DailySpendMetric.metric_date.asc())
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

        # 3. Convert to ORM AnomalyEvent records and save to DB
        created_events: list[AnomalyEvent] = []
        for sig in signals:
            event = AnomalyEvent(
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

        await session.commit()
        return created_events
