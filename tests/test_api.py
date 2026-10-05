"""
Automated Test Suite for FastAPI REST and SSE Streaming Endpoints.
Verifies health checks, KPI metrics overview, anomaly querying, and real-time SSE streams.
"""

import pytest
from httpx import AsyncClient


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
    # 1. FinTech partition
    res = await api_client.get("/api/v1/metrics/overview?dataset_source=FINTECH_90D")
    assert res.status_code == 200
    data = res.json()
    assert "total_spend_90d" in data
    assert "total_transactions" in data
    assert "avg_success_rate_pct" in data
    assert data["total_spend_90d"] > 0
    assert data["total_transactions"] > 0

    # 2. CFPB partition
    res_cfpb = await api_client.get("/api/v1/metrics/overview?dataset_source=KAGGLE_CFPB")
    assert res_cfpb.status_code == 200
    data_cfpb = res_cfpb.json()
    assert data_cfpb["total_transactions"] > 0
    assert data_cfpb["total_anomalies_detected"] > 0


@pytest.mark.asyncio
async def test_metrics_timeseries_endpoint(api_client: AsyncClient) -> None:
    # 1. FinTech timeseries
    res = await api_client.get("/api/v1/metrics/timeseries?dataset_source=FINTECH_90D")
    assert res.status_code == 200
    data = res.json()
    assert "dates" in data
    assert "spend" in data
    assert "success_rate" in data
    assert len(data["dates"]) > 0

    # 2. CFPB timeseries
    res_cfpb = await api_client.get("/api/v1/metrics/timeseries?dataset_source=KAGGLE_CFPB")
    assert res_cfpb.status_code == 200
    data_cfpb = res_cfpb.json()
    assert len(data_cfpb["dates"]) > 0


@pytest.mark.asyncio
async def test_serve_dashboard_endpoint(api_client: AsyncClient) -> None:
    res = await api_client.get("/")
    assert res.status_code == 200
    assert "InsightClue" in res.text
    assert "chart-timeseries" in res.text
    assert "app.js" in res.text
    assert "toast-container" in res.text
    assert "dataset-mode-select" in res.text

    # Verify static assets served
    res_js = await api_client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "startInvestigation" in res_js.text

    res_css = await api_client.get("/static/style.css")
    assert res_css.status_code == 200
    assert "dataset-selector-group" in res_css.text


@pytest.mark.asyncio
async def test_list_anomalies_endpoint(api_client: AsyncClient) -> None:
    # 1. Unfiltered query
    res = await api_client.get("/api/v1/anomalies?dataset_source=FINTECH_90D&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 10
    assert data["total"] > 0

    # 2. CFPB query
    res_cfpb = await api_client.get("/api/v1/anomalies?dataset_source=KAGGLE_CFPB&limit=10")
    assert res_cfpb.status_code == 200
    data_cfpb = res_cfpb.json()
    assert data_cfpb["total"] > 0


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
                ev = line.replace("event:", "").strip()
                events_received.append(ev)
                if ev == "complete":
                    break

        assert len(events_received) > 0
        assert "anomaly_info" in events_received
        assert "complete" in events_received
