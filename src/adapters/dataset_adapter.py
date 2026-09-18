"""
Universal Dataset Ingestion & Schema Adapter Seam.
Transforms arbitrary external datasets (CFPB Consumer Complaints, PaySim, IEEE-CIS)
into normalized InsightClue PostgreSQL & pgvector records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
import logging
from pathlib import Path
import sqlite3
from typing import Any
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.dispute_tickets import DisputeSupportTicket
from src.models.fintech_metrics import DailySpendMetric
from src.services.embedding_service import generate_embeddings_batch

logger = logging.getLogger(__name__)


@dataclass
class DatasetSchemaMapping:
    """
    Declarative schema mapping to normalize arbitrary source columns to InsightClue domain models.
    """
    date_col: str
    product_col: str
    issue_col: str
    text_col: str
    entity_id_col: str
    sub_product_col: str | None = None
    sub_issue_col: str | None = None
    company_col: str | None = None
    region_col: str | None = None
    disputed_col: str | None = None
    date_format: str | None = None  # e.g. "%m/%d/%Y" or None for auto-parser


# Preset configuration for Kaggle CFPB Consumer Complaints Dataset
CFPB_MAPPING = DatasetSchemaMapping(
    date_col="date_received",
    product_col="product",
    sub_product_col="sub_product",
    issue_col="issue",
    sub_issue_col="sub_issue",
    text_col="consumer_complaint_narrative",
    entity_id_col="complaint_id",
    company_col="company",
    region_col="state",
    disputed_col="consumer_disputed?",
    date_format="%m/%d/%Y",
)


@dataclass
class IngestionResult:
    """Summary result of a dataset ingestion run."""
    source_file: str
    total_parsed: int
    tickets_inserted: int
    daily_metrics_inserted: int
    duration_seconds: float


class UniversalDatasetAdapter:
    """
    Universal Seam for ingesting external FinTech and grievance datasets into InsightClue.
    """

    def __init__(self) -> None:
        pass

    def load_and_normalize_records(
        self,
        source_path: str | Path,
        mapping: DatasetSchemaMapping,
        max_records: int = 1000,
        filter_has_narrative: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Loads records from CSV or SQLite and normalizes them into structured dictionary items.
        """
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"Source dataset not found at: {path}")

        records: list[dict[str, Any]] = []

        if path.suffix.lower() == ".csv":
            # Determine needed columns for speed
            cols = [
                mapping.date_col,
                mapping.product_col,
                mapping.issue_col,
                mapping.text_col,
                mapping.entity_id_col,
            ]
            if mapping.sub_product_col:
                cols.append(mapping.sub_product_col)
            if mapping.company_col:
                cols.append(mapping.company_col)
            if mapping.region_col:
                cols.append(mapping.region_col)
            if mapping.disputed_col:
                cols.append(mapping.disputed_col)

            chunk_size = 50000
            for chunk in pd.read_csv(
                path,
                usecols=lambda c: c in cols,
                chunksize=chunk_size,
                low_memory=False,
                dtype=str,
            ):
                if filter_has_narrative and mapping.text_col in chunk.columns:
                    # Filter non-empty narrative
                    valid_mask = chunk[mapping.text_col].notna() & chunk[mapping.text_col].astype(str).str.strip().ne("") & chunk[mapping.text_col].astype(str).str.lower().ne("nan")
                    chunk = chunk[valid_mask]

                for _, row in chunk.iterrows():
                    norm = self._normalize_row(row, mapping)
                    if norm:
                        records.append(norm)
                    if len(records) >= max_records:
                        break
                if len(records) >= max_records:
                    break

        elif path.suffix.lower() in [".sqlite", ".db", ".sqlite3"]:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
            table_row = cur.fetchone()
            if not table_row:
                conn.close()
                raise ValueError(f"No tables found in SQLite database at {path}")
            
            table_name = table_row[0]
            query = f"SELECT * FROM {table_name}"
            if filter_has_narrative:
                query += f" WHERE {mapping.text_col} IS NOT NULL AND {mapping.text_col} != '' AND LOWER({mapping.text_col}) != 'nan'"
            query += f" LIMIT {max_records}"
            
            df = pd.read_sql_query(query, conn)
            conn.close()

            for _, row in df.iterrows():
                norm = self._normalize_row(row, mapping)
                if norm:
                    records.append(norm)

        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Expected .csv or .sqlite")

        logger.info(f"Loaded and normalized {len(records)} records from {path.name}")
        return records

    def _normalize_row(self, row: pd.Series, mapping: DatasetSchemaMapping) -> dict[str, Any] | None:
        """Helper to transform an individual raw dataset row to standardized fields."""
        try:
            raw_date = row.get(mapping.date_col)
            if pd.isna(raw_date):
                return None

            # Parse date safely
            if mapping.date_format:
                try:
                    parsed_dt = datetime.strptime(str(raw_date).strip(), mapping.date_format).replace(tzinfo=timezone.utc)
                except ValueError:
                    parsed_dt = pd.to_datetime(raw_date, errors="coerce").to_pydatetime()
                    if parsed_dt.tzinfo is None:
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            else:
                parsed_dt = pd.to_datetime(raw_date, errors="coerce").to_pydatetime()
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)

            # Region mapping (standardize US state or region)
            raw_region = str(row.get(mapping.region_col, "West")).strip() if mapping.region_col else "West"
            if not raw_region or raw_region.lower() == "nan":
                raw_region = "West"

            # Product & Category
            product = str(row.get(mapping.product_col, "Credit Card")).strip()
            issue = str(row.get(mapping.issue_col, "Account Dispute")).strip()
            narrative = str(row.get(mapping.text_col, "")).strip()

            if not narrative or narrative.lower() == "nan":
                return None

            # Customer tier heuristic based on company or product
            company = str(row.get(mapping.company_col, "Financial Institution")).strip()
            tier = "Enterprise" if "Corporate" in product or "Commercial" in product else "Retail"

            # Priority heuristic based on disputed flag
            is_disputed = str(row.get(mapping.disputed_col, "")).strip().lower() in ("yes", "true", "1")
            priority = "CRITICAL" if is_disputed else "NORMAL"

            entity_id = str(row.get(mapping.entity_id_col, f"TKT-{hash(narrative) % 1000000}"))

            return {
                "ticket_created_at": parsed_dt,
                "region": raw_region[:50],
                "product_name": product[:100],
                "customer_tier": tier,
                "customer_id": f"CUST-{entity_id[-6:]}",
                "issue_category": issue[:50],
                "priority": priority,
                "dispute_amount": 250.0 if is_disputed else 0.0,
                "sentiment_score": -0.7 if is_disputed else -0.3,
                "subject": f"[{product}] {issue}",
                "message": narrative,
                "company": company,
            }
        except Exception as e:
            logger.debug(f"Failed to normalize row: {e}")
            return None

    async def ingest_dispute_tickets(
        self,
        records: list[dict[str, Any]],
        session: AsyncSession,
        dataset_source: str = "KAGGLE_CFPB",
        batch_size: int = 50,
    ) -> int:
        """
        Embeds customer complaint narratives in batches and persists to dispute_support_tickets.
        """
        if not records:
            return 0

        import asyncio
        inserted_count = 0
        total = len(records)

        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]
            messages = [r["message"] for r in batch]

            # Generate 768-dim embeddings in batch via worker thread to prevent event-loop block
            embeddings = await asyncio.to_thread(generate_embeddings_batch, messages)

            for rec, emb in zip(batch, embeddings):
                ticket = DisputeSupportTicket(
                    dataset_source=dataset_source,
                    ticket_created_at=rec["ticket_created_at"],
                    region=rec["region"],
                    product_name=rec["product_name"],
                    customer_tier=rec["customer_tier"],
                    customer_id=rec["customer_id"],
                    issue_category=rec["issue_category"],
                    priority=rec["priority"],
                    dispute_amount=rec["dispute_amount"],
                    sentiment_score=rec["sentiment_score"],
                    subject=rec["subject"][:255],
                    message=rec["message"],
                    embedding=emb,
                )
                session.add(ticket)
                inserted_count += 1

            await session.commit()
            logger.info(f"Embedded and inserted {inserted_count}/{total} dispute tickets into pgvector.")

        return inserted_count

    async def aggregate_to_daily_metrics(
        self,
        records: list[dict[str, Any]],
        session: AsyncSession,
        dataset_source: str = "KAGGLE_CFPB",
    ) -> int:
        """
        Aggregates complaint counts and disputes into daily_spend_metrics for time-series anomaly scanning.
        """
        if not records:
            return 0

        df = pd.DataFrame(records)
        df["metric_date"] = df["ticket_created_at"].apply(lambda dt: dt.date())

        # Group by date, region, product_name, customer_tier
        grouped = df.groupby(["metric_date", "region", "product_name", "customer_tier"]).agg(
            complaint_count=("message", "count"),
            disputed_count=("priority", lambda p: (p == "CRITICAL").sum()),
        ).reset_index()

        inserted_count = 0
        for _, row in grouped.iterrows():
            complaint_count = int(row["complaint_count"])
            disputes = int(row["disputed_count"])
            chargeback_rate = (disputes / complaint_count * 100.0) if complaint_count > 0 else 0.0

            metric = DailySpendMetric(
                dataset_source=dataset_source,
                metric_date=row["metric_date"],
                region=str(row["region"]),
                product_name=str(row["product_name"]),
                customer_tier=str(row["customer_tier"]),
                merchant_category="CFPB Grievances",
                daily_spend_amount=float(complaint_count * 250.0),
                transaction_count=complaint_count,
                avg_ticket_size=250.0,
                success_rate_pct=max(100.0 - chargeback_rate, 5.0),
                avg_latency_ms=180.0 + (disputes * 40.0),
                chargeback_rate_pct=chargeback_rate,
                avg_fraud_risk_score=min(disputes * 20.0, 95.0),
            )
            session.add(metric)
            inserted_count += 1

        await session.commit()
        logger.info(f"Aggregated and persisted {inserted_count} DailySpendMetric rows.")
        return inserted_count

    async def ingest_dataset(
        self,
        source_path: str | Path,
        mapping: DatasetSchemaMapping,
        session: AsyncSession,
        max_records: int = 1000,
        dataset_source: str = "KAGGLE_CFPB",
    ) -> IngestionResult:
        """
        Full end-to-end ingestion pipeline: load, embed, and aggregate.
        """
        start_time = datetime.now(timezone.utc)

        records = self.load_and_normalize_records(source_path, mapping, max_records=max_records)
        tickets_count = await self.ingest_dispute_tickets(records, session, dataset_source=dataset_source)
        metrics_count = await self.aggregate_to_daily_metrics(records, session, dataset_source=dataset_source)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        return IngestionResult(
            source_file=Path(source_path).name,
            total_parsed=len(records),
            tickets_inserted=tickets_count,
            daily_metrics_inserted=metrics_count,
            duration_seconds=elapsed,
        )
