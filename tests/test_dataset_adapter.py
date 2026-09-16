"""
Unit and integration tests for UniversalDatasetAdapter & CFPB Dataset Ingestion.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.adapters.dataset_adapter import CFPB_MAPPING, DatasetSchemaMapping, UniversalDatasetAdapter
from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric


def test_schema_mapping_normalization():
    adapter = UniversalDatasetAdapter()
    data_dir = Path(__file__).resolve().parent.parent / "Data"
    csv_path = data_dir / "consumer_complaints.csv"

    if not csv_path.exists():
        pytest.skip("Data/consumer_complaints.csv not found in test environment.")

    # Load 10 sample records
    records = adapter.load_and_normalize_records(csv_path, CFPB_MAPPING, max_records=10)

    assert len(records) > 0
    first = records[0]
    assert "ticket_created_at" in first
    assert "product_name" in first
    assert "message" in first
    assert len(first["message"]) > 0
    assert first["customer_id"].startswith("CUST-")


def test_sqlite_loading():
    adapter = UniversalDatasetAdapter()
    data_dir = Path(__file__).resolve().parent.parent / "Data"
    sqlite_path = data_dir / "database.sqlite"

    if not sqlite_path.exists():
        pytest.skip("Data/database.sqlite not found in test environment.")

    records = adapter.load_and_normalize_records(sqlite_path, CFPB_MAPPING, max_records=10)
    assert len(records) > 0
    assert isinstance(records[0]["ticket_created_at"], datetime)


@pytest.mark.asyncio
async def test_dataset_adapter_ingest_and_aggregate(db_session: AsyncSession):
    adapter = UniversalDatasetAdapter()
    import uuid
    uid1 = f"CUST-{uuid.uuid4().hex[:6]}"
    uid2 = f"CUST-{uuid.uuid4().hex[:6]}"
    
    # Create 2 synthetic normalized test records
    sample_records = [
        {
            "ticket_created_at": datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc),
            "region": "West",
            "product_name": "Credit card",
            "customer_tier": "Retail",
            "customer_id": uid1,
            "issue_category": "Billing disputes",
            "priority": "CRITICAL",
            "dispute_amount": 350.0,
            "sentiment_score": -0.8,
            "subject": "[Credit card] Billing disputes",
            "message": "Unauthorized surcharge appeared on statement after merchant transaction.",
            "company": "Major FinTech Bank",
        },
        {
            "ticket_created_at": datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc),
            "region": "West",
            "product_name": "Credit card",
            "customer_tier": "Retail",
            "customer_id": uid2,
            "issue_category": "Billing disputes",
            "priority": "CRITICAL",
            "dispute_amount": 500.0,
            "sentiment_score": -0.9,
            "subject": "[Credit card] Billing disputes",
            "message": "Card was charged twice for a single international vendor checkout.",
            "company": "Major FinTech Bank",
        },
    ]

    # Ingest tickets
    inserted_tickets = await adapter.ingest_dispute_tickets(sample_records, db_session)
    assert inserted_tickets == 2

    # Verify embeddings are present in DB
    stmt = select(DisputeSupportTicket).where(DisputeSupportTicket.customer_id.in_([uid1, uid2]))
    res = await db_session.execute(stmt)
    tickets = res.scalars().all()
    assert len(tickets) == 2
    assert tickets[0].embedding is not None
    assert len(tickets[0].embedding) == 768

    # Aggregate to daily spend metrics
    inserted_metrics = await adapter.aggregate_to_daily_metrics(sample_records, db_session)
    assert inserted_metrics >= 1

    # Verify daily metric exists
    m_stmt = select(DailySpendMetric).where(
        DailySpendMetric.product_name == "Credit card",
        DailySpendMetric.region == "West",
    )
    m_res = await db_session.execute(m_stmt)
    metrics = m_res.scalars().all()
    assert len(metrics) > 0
    assert metrics[0].transaction_count >= 20
