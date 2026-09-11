"""
Automated Test Suite for FastAPI REST and SSE Streaming Endpoints.
Verifies health checks, KPI metrics overview, anomaly querying, and real-time SSE streams.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.api.main import app
from src.config.settings import get_settings
from src.database.session import get_db

settings = get_settings()


@pytest_asyncio.fixture
async def api_client():
    """Provides an async HTTP client with fresh connection pooling per test."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_pre_ping=True,
    )
    test_sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with test_sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_health_check_endpoints(api_client: AsyncClient) -> None:
    res = await api_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "app_name" in data

    res_v1 = await api_client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_metrics_overview_endpoint(api_client: AsyncClient) -> None:
    res = await api_client.get("/api/v1/metrics/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_spend_90d" in data
    assert "total_transactions" in data
    assert "avg_success_rate_pct" in data
    assert data["total_spend_90d"] > 0
    assert data["total_transactions"] > 0
    assert data["total_anomalies_detected"] > 0


@pytest.mark.asyncio
async def test_list_anomalies_endpoint(api_client: AsyncClient) -> None:
    # 1. Unfiltered query
    res = await api_client.get("/api/v1/anomalies?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 10
    assert data["total"] > 0

    # 2. Filter by region
    res_region = await api_client.get("/api/v1/anomalies?region=South&limit=5")
    assert res_region.status_code == 200
    region_data = res_region.json()
    for item in region_data["items"]:
        assert item["region"] == "South"


@pytest.mark.asyncio
async def test_get_single_anomaly_endpoint(api_client: AsyncClient) -> None:
    # Fetch list first to get an ID
    list_res = await api_client.get("/api/v1/anomalies?limit=1")
    items = list_res.json()["items"]
    assert len(items) > 0
    first_id = items[0]["id"]

    # Fetch by ID
    res = await api_client.get(f"/api/v1/anomalies/{first_id}")
    assert res.status_code == 200
    anomaly = res.json()
    assert anomaly["id"] == first_id
    assert "metric_name" in anomaly
    assert "severity" in anomaly


@pytest.mark.asyncio
async def test_sse_investigation_stream_endpoint(api_client: AsyncClient) -> None:
    # Fetch list to get an ID
    list_res = await api_client.get("/api/v1/anomalies?limit=1")
    first_id = list_res.json()["items"][0]["id"]

    # Stream SSE
    async with api_client.stream("GET", f"/api/v1/investigations/stream/{first_id}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events_received = []
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                events_received.append(line.replace("event:", "").strip())

        assert len(events_received) > 0
        assert "anomaly_info" in events_received
        assert "complete" in events_received
