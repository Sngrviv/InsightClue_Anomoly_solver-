"""
Deep Anomaly Detection Engine for InsightClue.
Combines generalized Rolling Statistical Z-Scores, Continuous Time-Series Gap Filling,
and Multi-Metric Isolation Forests behind a unified seam.
Supports multi-dataset source partitioning (FINTECH_90D, KAGGLE_CFPB).
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
from typing import Any, Sequence
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import AsyncSessionFactory
from src.models.fintech_metrics import DailySpendMetric
from src.models.investigations import AnomalyEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnomalySignal:
    """Represents a detected anomaly signal across time-series slices."""

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
    Encapsulates rolling statistical baselines, continuous calendar gap filling,
    multi-metric Isolation Forest modeling, and composite severity scoring.
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

    def scan_dataframe(
        self,
        df: pd.DataFrame,
        fill_calendar_gaps: bool = True,
    ) -> list[AnomalySignal]:
        """
        Scans a DataFrame of metric rows and returns ranked AnomalySignal objects.
        Dynamically handles varying columns and fills calendar gaps to maintain rolling window accuracy.
        """
        if df.empty:
            return []

        signals: list[AnomalySignal] = []
        df_copy = df.copy()

        # Ensure metric_date is datetime.date
        if not pd.api.types.is_datetime64_any_dtype(df_copy["metric_date"]):
            df_copy["parsed_date"] = pd.to_datetime(df_copy["metric_date"]).dt.date
        else:
            df_copy["parsed_date"] = df_copy["metric_date"].dt.date

        # Standard slice dimensions
        slice_cols = [c for c in ["region", "product_name", "customer_tier"] if c in df_copy.columns]
        if not slice_cols:
            grouped = [("ALL", df_copy)]
        else:
            grouped = df_copy.groupby(slice_cols)

        for group_keys, slice_raw in grouped:
            if isinstance(group_keys, tuple):
                region = str(group_keys[0]) if len(group_keys) > 0 else "All"
                product = str(group_keys[1]) if len(group_keys) > 1 else "All"
                tier = str(group_keys[2]) if len(group_keys) > 2 else "All"
            else:
                region = str(group_keys)
                product = "All"
                tier = "All"

            slice_df = slice_raw.sort_values(by="parsed_date").drop_duplicates(subset=["parsed_date"]).copy()

            # Record original dates before any gap filling
            observed_dates = set(slice_df["parsed_date"])

            # 1. Calendar Gap Filling
            if fill_calendar_gaps and len(slice_df) >= 3:
                min_d = slice_df["parsed_date"].min()
                max_d = slice_df["parsed_date"].max()
                full_range = pd.date_range(min_d, max_d, freq="D").date
                slice_df = slice_df.set_index("parsed_date").reindex(full_range)
                slice_df.index.name = "parsed_date"

                # Forward fill dimension names & metric rates; zero fill amounts if missing
                slice_df["region"] = slice_df["region"].ffill().bfill().fillna(region)
                slice_df["product_name"] = slice_df["product_name"].ffill().bfill().fillna(product)
                slice_df["customer_tier"] = slice_df["customer_tier"].ffill().bfill().fillna(tier)

                for col in ["success_rate_pct", "avg_latency_ms", "chargeback_rate_pct", "avg_fraud_risk_score"]:
                    if col in slice_df.columns:
                        slice_df[col] = slice_df[col].ffill().bfill()

                for col in ["daily_spend_amount", "transaction_count"]:
                    if col in slice_df.columns:
                        slice_df[col] = slice_df[col].fillna(0.0)

                slice_df = slice_df.reset_index()

            slice_len = len(slice_df)
            if slice_len < 3:
                continue

            # 2. Dynamic Rolling Statistics
            min_p = min(3, slice_len)
            win = min(self.rolling_window_days, slice_len)

            # A. Success Rate Plunge Detection
            if "success_rate_pct" in slice_df.columns:
                r_mean = slice_df["success_rate_pct"].rolling(window=win, min_periods=min_p).mean()
                r_std = slice_df["success_rate_pct"].rolling(window=win, min_periods=min_p).std().replace(0, 0.05).fillna(0.05)
                slice_df["z_sr"] = ((slice_df["success_rate_pct"] - r_mean) / r_std).fillna(0)
                slice_df["expected_sr"] = r_mean.fillna(slice_df["success_rate_pct"])

            # B. Latency Surge Detection
            if "avg_latency_ms" in slice_df.columns:
                r_mean = slice_df["avg_latency_ms"].rolling(window=win, min_periods=min_p).mean()
                r_std = slice_df["avg_latency_ms"].rolling(window=win, min_periods=min_p).std().replace(0, 5.0).fillna(5.0)
                slice_df["z_lat"] = ((slice_df["avg_latency_ms"] - r_mean) / r_std).fillna(0)
                slice_df["expected_lat"] = r_mean.fillna(slice_df["avg_latency_ms"])

            # C. Chargeback / Dispute Spike Detection
            if "chargeback_rate_pct" in slice_df.columns:
                r_mean = slice_df["chargeback_rate_pct"].rolling(window=win, min_periods=min_p).mean()
                r_std = slice_df["chargeback_rate_pct"].rolling(window=win, min_periods=min_p).std().replace(0, 0.05).fillna(0.05)
                slice_df["z_cb"] = ((slice_df["chargeback_rate_pct"] - r_mean) / r_std).fillna(0)
                slice_df["expected_cb"] = r_mean.fillna(slice_df["chargeback_rate_pct"])

            # 3. Multi-Metric Isolation Forest Ensemble
            feature_cols = [c for c in ["success_rate_pct", "avg_latency_ms", "chargeback_rate_pct", "daily_spend_amount"] if c in slice_df.columns]
            slice_df["iso_score"] = 0.0
            slice_df["is_iso_anom"] = False

            if len(feature_cols) >= 2 and slice_len >= 7:
                try:
                    iso = IsolationForest(
                        contamination=self.isolation_forest_contamination,
                        random_state=42,
                        n_estimators=50,
                    )
                    clean_features = slice_df[feature_cols].fillna(0.0)
                    preds = iso.fit_predict(clean_features)
                    scores = iso.decision_function(clean_features)
                    slice_df["iso_score"] = scores
                    slice_df["is_iso_anom"] = preds == -1
                except Exception as e:
                    logger.debug(f"[AnomalyEngine] IsolationForest skipped: {e}")

            # 4. Extract Anomaly Signals on Observed Dates
            for _, row in slice_df.iterrows():
                dt = row["parsed_date"]
                if dt not in observed_dates:
                    continue

                iso_sc = float(row.get("iso_score", 0.0))
                is_iso = bool(row.get("is_iso_anom", False))

                # Check Success Rate Plunge
                if "success_rate_pct" in row:
                    actual = float(row["success_rate_pct"])
                    expected = float(row.get("expected_sr", 99.0))
                    z_val = float(row.get("z_sr", 0.0))

                    # Must have a meaningful drop (actual <= expected - 2.0 or actual <= 95.0) in addition to z-score
                    if (z_val <= -self.z_score_threshold and (actual <= expected - 2.0 or actual <= 95.0)) or actual <= 85.0 or (is_iso and actual <= 92.0):
                        dev_pct = ((actual - expected) / expected) * 100.0 if expected > 0 else -50.0
                        severity = "CRITICAL" if actual <= 80.0 or z_val <= -3.5 else "HIGH"
                        signals.append(
                            AnomalySignal(
                                metric_date=dt,
                                region=region,
                                product_name=product,
                                customer_tier=tier,
                                metric_name="success_rate_plunge",
                                actual_value=actual,
                                expected_value=round(expected, 2),
                                deviation_pct=round(dev_pct, 2),
                                z_score=round(z_val, 2),
                                isolation_score=round(iso_sc, 4),
                                severity=severity,
                            )
                        )

                # Check Latency Surge
                if "avg_latency_ms" in row:
                    actual = float(row["avg_latency_ms"])
                    expected = float(row.get("expected_lat", 200.0))
                    z_val = float(row.get("z_lat", 0.0))

                    if (z_val >= self.z_score_threshold and actual >= 500.0) or actual >= 1500.0 or (is_iso and actual >= 800.0):
                        dev_pct = ((actual - expected) / expected) * 100.0 if expected > 0 else 100.0
                        severity = "CRITICAL" if actual >= 2000.0 or z_val >= 4.0 else "HIGH"
                        signals.append(
                            AnomalySignal(
                                metric_date=dt,
                                region=region,
                                product_name=product,
                                customer_tier=tier,
                                metric_name="avg_latency_surge",
                                actual_value=actual,
                                expected_value=round(expected, 2),
                                deviation_pct=round(dev_pct, 2),
                                z_score=round(z_val, 2),
                                isolation_score=round(iso_sc, 4),
                                severity=severity,
                            )
                        )

                # Check Chargeback / Dispute Spike
                if "chargeback_rate_pct" in row:
                    actual = float(row["chargeback_rate_pct"])
                    expected = float(row.get("expected_cb", 0.2))
                    z_val = float(row.get("z_cb", 0.0))

                    if actual >= 2.0 or (z_val >= self.z_score_threshold and actual >= 1.0) or (is_iso and actual >= 1.5):
                        dev_pct = ((actual - expected) / expected) * 100.0 if expected > 0 else 200.0
                        severity = "CRITICAL" if actual >= 5.0 else "HIGH"
                        signals.append(
                            AnomalySignal(
                                metric_date=dt,
                                region=region,
                                product_name=product,
                                customer_tier=tier,
                                metric_name="chargeback_dispute_spike",
                                actual_value=actual,
                                expected_value=round(expected, 2),
                                deviation_pct=round(dev_pct, 2),
                                z_score=round(z_val, 2),
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
        and atomically saves unique records to anomaly_events.
        """
        if session is not None:
            return await self._scan_and_save(session, dataset_source=dataset_source)

        async with AsyncSessionFactory() as fresh_session:
            async with fresh_session.begin():
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
        signals = self.scan_dataframe(df, fill_calendar_gaps=True)

        # 3. Fetch existing events to prevent duplicates
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
            existing_keys.add(key)

        await session.flush()

        # Return all persisted anomaly events for this dataset_source
        all_events_stmt = (
            select(AnomalyEvent)
            .where(AnomalyEvent.dataset_source == dataset_source)
            .order_by(AnomalyEvent.id.asc())
        )
        all_events_res = await session.execute(all_events_stmt)
        return list(all_events_res.scalars().all())
