"""
Real Ground-Truth Data Ingestion Engine for InsightClue.
Streams authentic Kaggle Consumer Complaints data directly from Data/database.sqlite / Data/consumer_complaints.csv
into PostgreSQL & pgvector, aggregates daily time-series metrics, and executes automated anomaly detection.
Zero synthetic fake generators.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from src.adapters.dataset_adapter import CFPB_MAPPING, UniversalDatasetAdapter
from src.database.base import Base
from src.database.session import AsyncSessionFactory, async_engine
from src.models import (
    AnomalyEvent,
    DailySpendMetric,
    DisputeSupportTicket,
    PaymentGatewayLog,
)
from src.services.anomaly_detector import AnomalyDetectionEngine
from src.services.ticket_vector_store import TicketVectorStore


async def recreate_tables():
    """Drops and re-creates all tables in PostgreSQL with pgvector extension enabled."""
    async with async_engine.begin() as conn:
        print("🛠️  Ensuring pgvector extension is enabled...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        print("🗑️  Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)

        print("🏗️  Creating new schema tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Schema created successfully.")


async def ingest_real_data(max_records: int = 1500):
    """
    Ingests authentic Kaggle dataset records from Data/ folder, computes embeddings,
    persists daily aggregated metrics, and triggers anomaly detection.
    """
    print("=" * 65)
    print("🚀 Starting InsightClue Authentic Data Ingestion Engine")
    print("=" * 65)

    await recreate_tables()

    adapter = UniversalDatasetAdapter()
    data_dir = PROJECT_ROOT / "Data"

    sqlite_path = data_dir / "database.sqlite"
    csv_path = data_dir / "consumer_complaints.csv"

    source_path = sqlite_path if sqlite_path.exists() else csv_path
    if not source_path.exists():
        raise FileNotFoundError(f"No authentic data file found in {data_dir}. Expected database.sqlite or consumer_complaints.csv")

    print(f"\n📂 Loading authentic ground-truth records from: {source_path.name} (Limit: {max_records:,} records)...")
    
    async with AsyncSessionFactory() as session:
        result = await adapter.ingest_dataset(
            source_path=source_path,
            mapping=CFPB_MAPPING,
            session=session,
            max_records=max_records,
            dataset_source="KAGGLE_CFPB",
        )

    print(f"✅ Ingestion Complete in {result.duration_seconds:.2f}s:")
    print(f"   - Parsed Records: {result.total_parsed:,}")
    print(f"   - Dispute Support Tickets Indexed: {result.tickets_inserted:,}")
    print(f"   - Daily Metric Time-Series Aggregated: {result.daily_metrics_inserted:,}")

    # Run Anomaly Detection on the Ingested Real Data
    print("\n🔍 Running AnomalyDetectionEngine on authentic ingested metrics...")
    engine = AnomalyDetectionEngine(rolling_window_days=7, z_score_threshold=2.0)
    async with AsyncSessionFactory() as session:
        events = await engine.scan_and_persist(session=session, dataset_source="KAGGLE_CFPB")

    print(f"🚨 Detected and Persisted {len(events)} Anomaly Events in KAGGLE_CFPB data.")

    # Verification Query
    print("\n" + "=" * 65)
    print("🎯 Verification & Semantic Vector Search Test")
    print("=" * 65)

    store = TicketVectorStore()
    test_query = "unauthorized transaction fee on credit card account"
    matches = await store.search(query=test_query, limit=3, dataset_source="KAGGLE_CFPB")

    print(f"Query: '{test_query}'")
    for i, m in enumerate(matches, 1):
        print(f" {i}. [Similarity: {m.similarity_score:.4f}] {m.ticket.subject} (State: {m.ticket.region})")
        print(f"    Message: {m.ticket.message[:120]}...\n")

    await async_engine.dispose()
    print("🎉 REAL DATA GROUNDING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    limit = 500
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit = int(sys.argv[1])
    asyncio.run(ingest_real_data(max_records=limit))
