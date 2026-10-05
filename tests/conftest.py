"""
Pytest configuration and shared async fixtures for InsightClue test suite.
Provides strict transactional test isolation with nested savepoints and automatic rollback.
Ensures no test fixture or route execution ever persists dirty data to the live database.
"""

from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from src.api.main import app
from src.config.settings import get_settings
from src.database.session import async_engine, get_db
from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric
from src.models.gateway_logs import PaymentGatewayLog
from src.models.investigations import AnomalyEvent

settings = get_settings()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_global_engine():
    """Automatically disposes global engine pool connections after each test to prevent loop leakage."""
    yield
    await async_engine.dispose()


@pytest_asyncio.fixture
async def db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """
    Provides an isolated database connection wrapped in an outer transaction.
    Rolls back the outer transaction on teardown to guarantee 100% clean test isolation.
    """
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        if trans.is_active:
            await trans.rollback()
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transactional AsyncSession bound to a nested savepoint.
    Any `session.commit()` inside tested code only commits the savepoint, never the outer transaction.
    """
    session = AsyncSession(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def seeded_db_session(db_session: AsyncSession) -> AsyncSession:
    """
    Populates db_session with deterministic baseline records for FinTech and CFPB.
    Automatically isolated to the test savepoint transaction and rolled back on teardown.
    """
    base_date = date(2026, 1, 1)

    # 1. FinTech 30-day baseline + Day 30 plunge
    for i in range(30):
        m_date = base_date + timedelta(days=i)
        sr = 99.0 if i < 29 else 74.0
        spend = 500000.0 if i < 29 else 250000.0
        lat = 250.0 if i < 29 else 1800.0
        db_session.add(
            DailySpendMetric(
                dataset_source="FINTECH_90D",
                metric_date=m_date,
                region="South",
                product_name="Corporate Credit Card",
                customer_tier="Enterprise",
                merchant_category="SaaS & Cloud Services",
                daily_spend_amount=spend,
                transaction_count=1000,
                avg_ticket_size=spend / 1000.0,
                success_rate_pct=sr,
                avg_latency_ms=lat,
                chargeback_rate_pct=0.1 if i < 29 else 3.5,
                avg_fraud_risk_score=5.0,
            )
        )

    # 2. CFPB metrics
    for i in range(10):
        m_date = date(2015, 3, 1) + timedelta(days=i)
        db_session.add(
            DailySpendMetric(
                dataset_source="KAGGLE_CFPB",
                metric_date=m_date,
                region="National",
                product_name="Credit card or prepaid card",
                customer_tier="General",
                merchant_category="Consumer Banking",
                daily_spend_amount=100000.0,
                transaction_count=50,
                avg_ticket_size=2000.0,
                success_rate_pct=90.0,
                avg_latency_ms=100.0,
                chargeback_rate_pct=1.0,
                avg_fraud_risk_score=10.0,
            )
        )

    # 3. Anomaly Events
    db_session.add(
        AnomalyEvent(
            dataset_source="FINTECH_90D",
            detected_at=datetime.now(timezone.utc),
            metric_name="success_rate_plunge",
            region="South",
            product_name="Corporate Credit Card",
            customer_tier="Enterprise",
            actual_value=74.0,
            expected_value=98.5,
            deviation_pct=-24.87,
            z_score=-20.4,
            severity="CRITICAL",
            status="OPEN",
        )
    )
    db_session.add(
        AnomalyEvent(
            dataset_source="KAGGLE_CFPB",
            detected_at=datetime.now(timezone.utc),
            metric_name="dispute_rate_spike",
            region="National",
            product_name="Credit card or prepaid card",
            customer_tier="General",
            actual_value=15.0,
            expected_value=2.0,
            deviation_pct=650.0,
            z_score=8.5,
            severity="HIGH",
            status="OPEN",
        )
    )

    # 4. Payment Gateway Logs
    db_session.add(
        PaymentGatewayLog(
            log_date=base_date + timedelta(days=29),
            region="South",
            partner_bank="HDFC Bank",
            product_name="Corporate Credit Card",
            gateway_channel="3DS_OTP",
            total_requests=1000,
            successful_requests=500,
            failed_requests=500,
            timeout_504_count=350,
            server_error_500_count=150,
            avg_response_time_ms=1850.0,
            gateway_status="DEGRADED",
        )
    )

    # 5. Dispute Support Tickets with pgvector embeddings
    from src.services.ticket_vector_store import _compute_embeddings_batch

    msg_fintech = "Corporate Card OTP timeout in South region with 3DS authorization failures."
    msg_cfpb = "Unexpected fee charged without prior notification on statement."
    embs = _compute_embeddings_batch([msg_fintech, msg_cfpb])

    db_session.add(
        DisputeSupportTicket(
            dataset_source="FINTECH_90D",
            ticket_created_at=datetime.now(timezone.utc),
            region="South",
            product_name="Corporate Credit Card",
            customer_tier="Enterprise",
            customer_id="CUST-ENT-901",
            issue_category="3DS_OTP_FAILURE",
            priority="CRITICAL",
            dispute_amount=4500.0,
            sentiment_score=-0.85,
            subject="Corporate Card OTP timeout in South region",
            message=msg_fintech,
            embedding=embs[0],
        )
    )
    db_session.add(
        DisputeSupportTicket(
            dataset_source="KAGGLE_CFPB",
            ticket_created_at=datetime.now(timezone.utc),
            region="National",
            product_name="Credit card or prepaid card",
            customer_tier="General",
            customer_id="CFPB-001",
            issue_category="Billing disputes",
            priority="HIGH",
            dispute_amount=1200.0,
            sentiment_score=-0.70,
            subject="Unrecognized billing dispute fee",
            message=msg_cfpb,
            embedding=embs[1],
        )
    )

    await db_session.commit()
    return db_session


@pytest_asyncio.fixture
async def api_client(seeded_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an asynchronous HTTP test client for FastAPI with dependency override for `get_db`.
    All HTTP requests share the test's isolated savepoint session and roll back automatically.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
