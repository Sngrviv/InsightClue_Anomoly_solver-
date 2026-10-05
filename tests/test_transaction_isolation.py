"""
Tests verifying the transactional test isolation seam.
Ensures that rows committed within db_session are rolled back automatically
and never leak to other sessions or persist in the live database.
"""

from datetime import date
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.config.settings import get_settings
from src.models.fintech_metrics import DailySpendMetric

settings = get_settings()


@pytest.mark.asyncio
async def test_session_commit_rolls_back_on_teardown(db_session: AsyncSession):
    """Verify that records inserted and committed inside db_session exist inside the test."""
    test_metric = DailySpendMetric(
        metric_date=date(2099, 1, 1),
        region="TestRegion",
        product_name="TestProduct",
        customer_tier="Enterprise",
        merchant_category="Tech",
        daily_spend_amount=99999.0,
        transaction_count=100,
        avg_ticket_size=999.99,
        success_rate_pct=100.0,
        avg_latency_ms=10.0,
        chargeback_rate_pct=0.01,
        avg_fraud_risk_score=1.5,
        dataset_source="TEST_ISOLATION_PROBE",
    )
    db_session.add(test_metric)
    await db_session.commit()

    # Query within the same session
    stmt = select(DailySpendMetric).where(
        DailySpendMetric.dataset_source == "TEST_ISOLATION_PROBE"
    )
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].region == "TestRegion"


@pytest.mark.asyncio
async def test_database_is_clean_after_previous_test():
    """Verify that records from test_session_commit_rolls_back_on_teardown did NOT leak into the DB."""
    standalone_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
    )
    async with AsyncSession(standalone_engine) as session:
        stmt = select(DailySpendMetric).where(
            DailySpendMetric.dataset_source == "TEST_ISOLATION_PROBE"
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        assert len(records) == 0, f"Found leaked records: {records}"
    await standalone_engine.dispose()
