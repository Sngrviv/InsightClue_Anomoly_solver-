"""
Automated unit & integration tests for AnomalyDetectionEngine.
Tests rolling Z-scores, multi-metric Isolation Forest, continuous calendar gap filling, and atomic deduplication.
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


def test_anomaly_detection_calendar_gap_filling():
    """Verifies that sparse time-series with missing date gaps are smoothly interpolated for rolling statistics."""
    engine = AnomalyDetectionEngine(rolling_window_days=7, z_score_threshold=2.0)

    # Create sparse records with a 10-day gap
    base_date = date(2026, 2, 1)
    records = [
        {"metric_date": base_date, "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.5, "avg_latency_ms": 120.0, "daily_spend_amount": 10000.0, "chargeback_rate_pct": 0.05},
        {"metric_date": base_date + timedelta(days=1), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.4, "avg_latency_ms": 130.0, "daily_spend_amount": 10500.0, "chargeback_rate_pct": 0.04},
        {"metric_date": base_date + timedelta(days=2), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.2, "avg_latency_ms": 125.0, "daily_spend_amount": 9800.0, "chargeback_rate_pct": 0.06},
        # Gap of 7 days
        {"metric_date": base_date + timedelta(days=10), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.1, "avg_latency_ms": 140.0, "daily_spend_amount": 11000.0, "chargeback_rate_pct": 0.05},
        {"metric_date": base_date + timedelta(days=11), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.3, "avg_latency_ms": 135.0, "daily_spend_amount": 10200.0, "chargeback_rate_pct": 0.04},
        {"metric_date": base_date + timedelta(days=12), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.0, "avg_latency_ms": 120.0, "daily_spend_amount": 10800.0, "chargeback_rate_pct": 0.05},
        {"metric_date": base_date + timedelta(days=13), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.2, "avg_latency_ms": 125.0, "daily_spend_amount": 10400.0, "chargeback_rate_pct": 0.05},
        {"metric_date": base_date + timedelta(days=14), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 99.4, "avg_latency_ms": 130.0, "daily_spend_amount": 10600.0, "chargeback_rate_pct": 0.04},
        {"metric_date": base_date + timedelta(days=15), "region": "West", "product_name": "UPI Instant Pay", "customer_tier": "Retail", "success_rate_pct": 60.0, "avg_latency_ms": 2500.0, "daily_spend_amount": 2000.0, "chargeback_rate_pct": 8.5},
    ]

    df = pd.DataFrame(records)
    signals = engine.scan_dataframe(df, fill_calendar_gaps=True)

    assert len(signals) >= 1
    anom = signals[0]
    assert anom.metric_date == base_date + timedelta(days=15)
    assert anom.severity == "CRITICAL"


@pytest.mark.asyncio
async def test_anomaly_detector_scan_and_persist_db(db_session: AsyncSession):
    engine = AnomalyDetectionEngine(rolling_window_days=14, z_score_threshold=2.5)

    events_first_pass = await engine.scan_and_persist(session=db_session)
    assert len(events_first_pass) > 0

    # Planted Anomaly in South region is discovered
    south_events = [
        e for e in events_first_pass
        if e.region == "South" and e.product_name == "Corporate Credit Card"
    ]
    assert len(south_events) > 0
    assert any(e.severity == "CRITICAL" for e in south_events)

    # Second pass: Assert atomic deduplication (no new duplicates inserted)
    events_second_pass = await engine.scan_and_persist(session=db_session)
    assert len(events_second_pass) == len(events_first_pass)
