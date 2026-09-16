"""
CLI Utility to ingest Kaggle CFPB Consumer Complaints dataset into InsightClue.
Normalizes complaint narratives, computes 768-dim embeddings in batch,
and aggregates time-series telemetry into PostgreSQL.
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.dataset_adapter import CFPB_MAPPING, UniversalDatasetAdapter
from src.database.session import AsyncSessionFactory


async def main():
    parser = argparse.ArgumentParser(description="InsightClue: Ingest external Kaggle / CFPB datasets.")
    parser.add_argument(
        "--source",
        type=str,
        default=str(PROJECT_ROOT / "Data" / "consumer_complaints.csv"),
        help="Path to CSV or SQLite dataset file (default: Data/consumer_complaints.csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum records with valid narrative to ingest and embed (default: 500)",
    )

    args = parser.parse_args()
    source_path = Path(args.source)

    print("=" * 65)
    print("📂 InsightClue: Kaggle CFPB Dataset Ingestion & Vector Embedding")
    print("=" * 65)
    print(f"• Source File : {source_path.resolve()}")
    print(f"• Sample Limit: {args.limit} complaint narratives")
    print("-" * 65)

    if not source_path.exists():
        print(f"❌ Error: File not found at {source_path}")
        return

    adapter = UniversalDatasetAdapter()

    print("\n⏳ Ingesting, parsing, and computing 768-dim semantic embeddings...")
    start_t = datetime.now()

    async with AsyncSessionFactory() as session:
        result = await adapter.ingest_dataset(
            source_path=source_path,
            mapping=CFPB_MAPPING,
            session=session,
            max_records=args.limit,
        )

    duration = (datetime.now() - start_t).total_seconds()
    print("\n" + "=" * 65)
    print("🎉 Ingestion & Vector Embedding Complete!")
    print("=" * 65)
    print(f"• Total Records Parsed        : {result.total_parsed:,}")
    print(f"• Dispute Tickets Ingested (PG): {result.tickets_inserted:,}")
    print(f"• Daily Spend Metrics Aggregated: {result.daily_metrics_inserted:,}")
    print(f"• Total Duration               : {duration:.2f} seconds")
    print("=" * 65)
    print("💡 Next Step: Run 'uv run python scripts/run_anomaly_detection.py' to scan for anomalies!")


if __name__ == "__main__":
    asyncio.run(main())
