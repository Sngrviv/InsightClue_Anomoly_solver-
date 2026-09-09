"""
Automated unit & integration tests for AnomalyDetectionEngine.
"""

from datetime import date, timedelta
import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.anomaly_detector import AnomalyDetectionEngine


def test_anomaly_detection_engine_statistical_and_isolation():
    engine = AnomalyDetectionEngine(rolling_window_days=7, z_score_threshold=2.0)

    # Build 30 days of baseline test data + 1 injected drop
    records = []
    base_date = date(2026, 1, 1)
    for i in range(30):
        sr = 99.0
        if i == 25:
            sr = 75.0  # Massive 24% plunge

        records.append(
            {
                "metric_date": base_date + timedelta(days=i),
                "region": "South",
                "product_name": "Corporate Credit Card",
                "customer_tier": "Enterprise",
                "merchant_category": "SaaS & Cloud Services",
                "daily_spend_amount": 500000.0 if i != 25 else 250000.0,
                "transaction_count": 100,
                "success_rate_pct": sr,
                "avg_latency_ms": 250.0 if i != 25 else 1800.0,
                "chargeback_rate_pct": 0.1,
                "avg_fraud_risk_score": 5.0,
            }
        )

    df = pd.DataFrame(records)
    signals = engine.scan_dataframe(df)

    assert len(signals) >= 1
    plunge_signal = [s for s in signals if s.metric_name == "success_rate_plunge"][0]
    assert plunge_signal.metric_date == base_date + timedelta(days=25)
    assert plunge_signal.actual_value == 75.0
    assert plunge_signal.z_score < -2.0
    assert plunge_signal.severity in ["HIGH", "CRITICAL"]


@pytest.mark.asyncio
async def test_anomaly_detector_scan_and_persist_db(db_session: AsyncSession):
    engine = AnomalyDetectionEngine(rolling_window_days=14, z_score_threshold=2.5)

    events = await engine.scan_and_persist(session=db_session)

    # Assert that planted anomalies in DB are discovered
    assert len(events) > 0

    # Assert Planted Anomaly 1 (South, Corporate Card) is detected
    south_events = [
        e for e in events
        if e.region == "South" and e.product_name == "Corporate Credit Card"
    ]
    assert len(south_events) > 0
    assert any(e.severity == "CRITICAL" for e in south_events)
