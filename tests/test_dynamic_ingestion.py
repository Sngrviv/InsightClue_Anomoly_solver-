"""
Test suite for DynamicIngestionEngine.
Tests schema inference, multi-format parsing, chunked ingestion, FastEmbed ONNX indexing,
and API route contracts under transactional rollback isolation.
"""

import io
import pytest
from src.services.dynamic_ingestion import DynamicIngestionEngine, InferredSchema, DatasetMapping


def test_infer_schema_csv_with_mixed_columns():
    """
    Tests that DynamicIngestionEngine correctly infers:
    - timestamp_col (e.g. 'txn_timestamp')
    - metric_cols and primary_metric (e.g. 'amount', 'fee')
    - dimension_cols (e.g. 'merchant_id', 'currency', 'status')
    - narrative_col (e.g. 'failure_reason')
    """
    csv_content = (
        "txn_timestamp,merchant_id,amount,fee,currency,status,failure_reason\n"
        "2026-03-01 10:00:00,M_101,150.50,3.20,USD,FAILED,Card issuer timeout\n"
        "2026-03-01 10:05:00,M_102,99.00,2.10,USD,SUCCESS,None\n"
        "2026-03-01 10:10:00,M_101,420.00,8.50,EUR,FAILED,Insufficient funds\n"
    ).encode("utf-8")

    schema = DynamicIngestionEngine.infer_schema(csv_content, filename="payment_gateway_logs.csv")

    assert isinstance(schema, InferredSchema)
    assert schema.dataset_name == "payment_gateway_logs"
    assert schema.timestamp_col == "txn_timestamp"
    assert "amount" in schema.metric_cols
    assert "fee" in schema.metric_cols
    assert schema.primary_metric in ["amount", "fee"]
    assert "merchant_id" in schema.dimension_cols
    assert "currency" in schema.dimension_cols
    assert schema.narrative_col == "failure_reason"
    assert schema.row_count == 3


def test_infer_schema_json_pure_numerical():
    """
    Tests schema inference on pure numerical DevOps/server metrics JSON with no narrative text.
    """
    json_content = b"""[
        {"timestamp": "2026-03-01T00:00:00Z", "server_id": "srv-01", "region": "us-east", "cpu_percent": 88.5, "latency_ms": 240},
        {"timestamp": "2026-03-01T00:01:00Z", "server_id": "srv-02", "region": "us-west", "cpu_percent": 45.0, "latency_ms": 120}
    ]"""

    schema = DynamicIngestionEngine.infer_schema(json_content, filename="server_metrics.json")

    assert schema.dataset_name == "server_metrics"
    assert schema.timestamp_col == "timestamp"
    assert "cpu_percent" in schema.metric_cols
    assert "latency_ms" in schema.metric_cols
    assert "server_id" in schema.dimension_cols
    assert schema.narrative_col is None
    assert schema.row_count == 2


@pytest.mark.asyncio
async def test_ingest_custom_dataset_with_embeddings(db_session):
    """
    Tests that DynamicIngestionEngine.ingest_dataset commits telemetry records and
    generates FastEmbed ONNX embeddings into support_tickets for a custom dataset.
    """
    from src.services.telemetry_store import TelemetryMetricStore
    from src.services.ticket_vector_store import TicketVectorStore

    csv_content = (
        "event_time,region,product,amount,customer_notes\n"
        "2026-03-01 10:00:00,North,Enterprise Card,500.0,Customer reported 3DS timeout at merchant\n"
        "2026-03-01 11:00:00,North,Enterprise Card,250.0,Customer disputed unauthorized charge\n"
        "2026-03-02 09:00:00,South,Standard Card,120.0,Smooth transaction with zero latency\n"
    ).encode("utf-8")

    mapping = DatasetMapping(
        dataset_name="custom_fintech_2026",
        timestamp_col="event_time",
        primary_metric="amount",
        metric_cols=["amount"],
        dimension_cols=["region", "product"],
        narrative_col="customer_notes",
    )

    summary = await DynamicIngestionEngine.ingest_dataset(
        db=db_session,
        content=csv_content,
        filename="custom_fintech_2026.csv",
        mapping=mapping,
    )

    assert summary.dataset_name == "custom_fintech_2026"
    assert summary.total_records == 3
    assert summary.metrics_inserted >= 2
    assert summary.tickets_embedded == 3

    # 1. Verify telemetry metrics accessible via TelemetryMetricStore
    telemetry_store = TelemetryMetricStore()
    overview = await telemetry_store.get_overview(dataset_source="custom_fintech_2026", session=db_session)
    assert overview.total_spend_90d >= 870.0
    assert overview.total_transactions == 3

    # 2. Verify semantic search works on the custom dataset
    ticket_store = TicketVectorStore()
    tickets = await ticket_store.search(
        query="timeout authorization issue",
        dataset_source="custom_fintech_2026",
        min_similarity=0.30,
        limit=2,
        session=db_session,
    )
    assert len(tickets) > 0
    assert "timeout" in tickets[0].ticket.message.lower() or "disputed" in tickets[0].ticket.message.lower()


@pytest.mark.asyncio
async def test_api_upload_schema_inference(api_client):
    """
    Tests POST /api/datasets/upload endpoint returns inferred schema for uploaded CSV.
    """
    csv_file = io.BytesIO(
        b"created_at,server_name,cpu_pct,error_rate,logs\n"
        b"2026-03-01 00:00:00,srv-east-1,75.0,0.02,High CPU utilization alert\n"
        b"2026-03-01 01:00:00,srv-west-1,40.0,0.00,Normal operation\n"
    )

    response = await api_client.post(
        "/api/datasets/upload",
        files={"file": ("cloud_telemetry.csv", csv_file, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dataset_name"] == "cloud_telemetry"
    assert data["timestamp_col"] == "created_at"
    assert "cpu_pct" in data["metric_cols"]
    assert "error_rate" in data["metric_cols"]
    assert data["narrative_col"] == "logs"
    assert data["row_count"] == 2


@pytest.mark.asyncio
async def test_api_ingest_and_list_datasets(api_client):
    """
    Tests POST /api/datasets/ingest and GET /api/datasets endpoints.
    """
    csv_file = io.BytesIO(
        b"event_time,region,product,amount,notes\n"
        b"2026-03-01 10:00:00,North,Debit Card,150.0,Payment timeout at POS\n"
        b"2026-03-01 11:00:00,North,Debit Card,300.0,Card declined by issuer\n"
    )

    mapping_json = (
        '{"dataset_name": "pos_debit_logs", "timestamp_col": "event_time", '
        '"primary_metric": "amount", "metric_cols": ["amount"], '
        '"dimension_cols": ["region", "product"], "narrative_col": "notes"}'
    )

    response = await api_client.post(
        "/api/datasets/ingest",
        files={"file": ("pos_debit_logs.csv", csv_file, "text/csv")},
        data={"mapping": mapping_json},
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["dataset_name"] == "pos_debit_logs"
    assert res_data["total_records"] == 2
    assert res_data["tickets_embedded"] == 2

    # Verify dataset appears in list_datasets endpoint
    list_resp = await api_client.get("/api/datasets")
    assert list_resp.status_code == 200
    datasets = list_resp.json()
    assert "pos_debit_logs" in datasets


@pytest.mark.asyncio
async def test_investigate_custom_uploaded_dataset(db_session):
    """
    Tests that AnomalyDetectionEngine and InvestigationService run autonomously
    over an uploaded dataset partition, producing a valid InvestigationReport.
    """
    from datetime import date, timedelta
    from src.services.anomaly_detector import AnomalyDetectionEngine
    from src.services.investigation_service import InvestigationService

    # 1. Ingest 15 days of baseline + Day 15 plunge
    rows = ["date,region,service,error_count,incident_log"]
    base_d = date(2026, 4, 1)
    for i in range(15):
        d_str = (base_d + timedelta(days=i)).isoformat()
        err = 5 if i < 14 else 180  # massive spike on day 15
        note = "Normal operational traffic" if i < 14 else "Gateway timeout on payment provider webhook"
        rows.append(f"{d_str},EU-Central,PaymentWebhook,{err},{note}")

    csv_content = "\n".join(rows).encode("utf-8")

    mapping = DatasetMapping(
        dataset_name="ecommerce_orders_2026",
        timestamp_col="date",
        primary_metric="error_count",
        metric_cols=["error_count"],
        dimension_cols=["region", "service"],
        narrative_col="incident_log",
    )

    await DynamicIngestionEngine.ingest_dataset(
        db=db_session,
        content=csv_content,
        filename="ecommerce_orders_2026.csv",
        mapping=mapping,
    )

    # 2. Run Anomaly Detection on the custom dataset
    detector = AnomalyDetectionEngine(rolling_window_days=7, z_score_threshold=2.0)
    anomalies = await detector.scan_and_persist(session=db_session, dataset_source="ecommerce_orders_2026")
    assert len(anomalies) > 0
    anom = anomalies[0]
    assert anom.dataset_source == "ecommerce_orders_2026"

    # 3. Run Autonomous Multi-Agent Investigation
    investigation_service = InvestigationService()
    report = await investigation_service.run_investigation(anomaly_id=anom.id, session=db_session)

    assert report is not None
    assert report.anomaly_id == anom.id
    assert report.confidence_score > 0.0
    assert len(report.root_cause_summary) > 0



