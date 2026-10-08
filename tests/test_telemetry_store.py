"""
Unit and integration tests for the deep TelemetryMetricStore seam.
Verifies aggregation invariants, timeseries windowing, and dataset source discovery.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.telemetry_store import TelemetryMetricStore


@pytest.mark.asyncio
async def test_telemetry_store_get_overview_fintech(seeded_db_session: AsyncSession):
    store = TelemetryMetricStore()
    overview = await store.get_overview("FINTECH_90D", session=seeded_db_session)

    assert overview.total_spend_90d > 0
    assert overview.total_transactions > 0
    assert 0.0 <= overview.avg_success_rate_pct <= 100.0
    assert overview.total_anomalies_detected >= 1
    assert overview.open_anomalies_count >= 1


@pytest.mark.asyncio
async def test_telemetry_store_get_overview_cfpb(seeded_db_session: AsyncSession):
    store = TelemetryMetricStore()
    overview = await store.get_overview("KAGGLE_CFPB", session=seeded_db_session)

    assert overview.total_transactions > 0
    assert overview.total_anomalies_detected >= 1


@pytest.mark.asyncio
async def test_telemetry_store_get_timeseries(seeded_db_session: AsyncSession):
    store = TelemetryMetricStore()
    ts = await store.get_timeseries("FINTECH_90D", session=seeded_db_session)

    assert ts["dataset_source"] == "FINTECH_90D"
    assert len(ts["dates"]) > 0
    assert len(ts["spend"]) == len(ts["dates"])
    assert len(ts["success_rate"]) == len(ts["dates"])
    assert len(ts["transactions"]) == len(ts["dates"])
    assert len(ts["dispute_rate"]) == len(ts["dates"])


@pytest.mark.asyncio
async def test_telemetry_store_list_datasets(seeded_db_session: AsyncSession):
    store = TelemetryMetricStore()
    datasets = await store.list_datasets(session=seeded_db_session)

    assert isinstance(datasets, list)
    assert "FINTECH_90D" in datasets
    assert "KAGGLE_CFPB" in datasets
