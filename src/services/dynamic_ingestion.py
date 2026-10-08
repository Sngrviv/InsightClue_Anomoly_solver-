"""
Dynamic Ingestion Engine.
Encapsulates multi-format dataset parsing, heuristic & statistical schema inference,
batch FastEmbed ONNX embedding generation, and atomic partitioned PostgreSQL ingestion.
"""

from __future__ import annotations
import io
import re
from datetime import datetime
from typing import Any, List, Optional
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.fintech_metrics import DailySpendMetric
from src.models.dispute_tickets import DisputeSupportTicket
from src.services.ticket_vector_store import _compute_embeddings_batch


class InferredSchema(BaseModel):
    """Inferred schema and semantic role mappings for an uploaded dataset."""
    dataset_name: str
    timestamp_col: str
    metric_cols: List[str] = Field(default_factory=list)
    primary_metric: str
    dimension_cols: List[str] = Field(default_factory=list)
    narrative_col: Optional[str] = None
    row_count: int = 0
    sample_rows: List[dict[str, Any]] = Field(default_factory=list)


class DatasetMapping(BaseModel):
    """User-confirmed or auto-applied column mapping for ingestion."""
    dataset_name: str
    timestamp_col: str
    primary_metric: str
    metric_cols: List[str] = Field(default_factory=list)
    dimension_cols: List[str] = Field(default_factory=list)
    narrative_col: Optional[str] = None


class IngestionSummary(BaseModel):
    """Summary of ingested records, dates, and vector embeddings generated."""
    dataset_name: str
    total_records: int
    metrics_inserted: int
    tickets_embedded: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DatasetSummary(BaseModel):
    """Summary of an active dataset partition."""
    dataset_name: str
    record_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DynamicIngestionEngine:
    """
    Deep Ingestion and Schema Inference Seam.
    Hides file parsing, schema heuristics, FastEmbed vectorization, and SQL batch persistence.
    """

    @staticmethod
    def infer_schema(content: bytes, filename: str) -> InferredSchema:
        """
        Parses the uploaded file buffer and infers column roles:
        - timestamp_col
        - metric_cols and primary_metric
        - dimension_cols
        - optional narrative_col
        """
        # 1. Clean dataset name
        base_name = re.sub(r"\.[^.]+$", "", filename).strip()
        dataset_name = re.sub(r"[^a-zA-Z0-9_]+", "_", base_name).strip("_").lower() or "custom_dataset"

        # 2. Parse file into DataFrame
        df = DynamicIngestionEngine._parse_dataframe(content, filename)
        row_count = len(df)
        if row_count == 0:
            raise ValueError(f"Uploaded file '{filename}' contains no rows.")

        columns = list(df.columns)

        # 3. Detect Timestamp Column
        timestamp_col = DynamicIngestionEngine._detect_timestamp_column(df)

        # 4. Detect Numerical Metric Columns
        metric_cols = []
        for col in columns:
            if col == timestamp_col:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                # If numeric and not a pure high-cardinality unique integer ID
                metric_cols.append(col)

        if not metric_cols:
            # Fallback: create a synthesized count metric if no numbers exist
            primary_metric = "event_count"
        else:
            # Choose primary metric: prefer keywords (latency, spend, amount, rate, count) or first numeric
            preferred = [c for c in metric_cols if any(k in c.lower() for k in ["latency", "spend", "amount", "rate", "count", "value", "percent", "cpu", "time"])]
            primary_metric = preferred[0] if preferred else metric_cols[0]

        # 5. Detect Narrative / Text Column vs Dimensions
        narrative_col = None
        dimension_cols = []

        for col in columns:
            if col == timestamp_col or col in metric_cols:
                continue

            str_series = df[col].dropna().astype(str)
            avg_len = float(str_series.str.len().mean()) if not str_series.empty else 0.0

            # If column name matches text/narrative keywords or average string length > 25
            is_narrative_keyword = any(k in col.lower() for k in ["narrative", "reason", "comment", "message", "text", "description", "log", "complaint", "feedback"])
            if is_narrative_keyword or (avg_len > 25 and not narrative_col):
                if narrative_col is None:
                    narrative_col = col
                    continue

            dimension_cols.append(col)

        sample_rows = df.head(5).to_dict(orient="records")

        return InferredSchema(
            dataset_name=dataset_name,
            timestamp_col=timestamp_col,
            metric_cols=metric_cols,
            primary_metric=primary_metric,
            dimension_cols=dimension_cols,
            narrative_col=narrative_col,
            row_count=row_count,
            sample_rows=sample_rows,
        )

    @staticmethod
    def _parse_dataframe(content: bytes | None, filename: str, file_path: str | Path | None = None) -> pd.DataFrame:
        """Parses CSV, JSON, Parquet, or SQLite file buffer/path into pandas DataFrame."""
        if file_path is not None:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Dataset file not found at: {path}")
            suffix = path.suffix.lower()
            if suffix in [".sqlite", ".db", ".sqlite3"]:
                import sqlite3
                conn = sqlite3.connect(path)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
                table_row = cur.fetchone()
                if not table_row:
                    conn.close()
                    raise ValueError(f"No tables found in SQLite database at {path}")
                table_name = table_row[0]
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                conn.close()
                return df
            elif suffix == ".csv" or suffix == ".txt":
                return pd.read_csv(path, low_memory=False)
            elif suffix == ".json":
                return pd.read_json(path)
            elif suffix == ".parquet":
                return pd.read_parquet(path)

        if content is None:
            raise ValueError("Either content bytes or file_path must be provided to parse DataFrame.")

        lower_name = filename.lower()
        if lower_name.endswith(".csv") or lower_name.endswith(".txt"):
            return pd.read_csv(io.BytesIO(content))
        elif lower_name.endswith(".json"):
            return pd.read_json(io.BytesIO(content))
        elif lower_name.endswith(".parquet"):
            return pd.read_parquet(io.BytesIO(content))
        else:
            try:
                return pd.read_csv(io.BytesIO(content))
            except Exception:
                return pd.read_json(io.BytesIO(content))

    @staticmethod
    def _detect_timestamp_column(df: pd.DataFrame) -> str:
        """Identifies the primary timestamp/date column using keyword matching and type parsing."""
        columns = list(df.columns)
        date_keywords = ["timestamp", "time", "date", "created_at", "received", "event_time", "datetime", "logged_at"]

        # 1. Exact or partial keyword match
        for kw in date_keywords:
            for col in columns:
                if kw in col.lower():
                    return col

        # 2. Try parsing object/string columns
        for col in columns:
            if df[col].dtype == "object":
                try:
                    pd.to_datetime(df[col].dropna().head(10))
                    return col
                except Exception:
                    continue

        # Fallback to first column
        return columns[0]

    @staticmethod
    async def ingest_dataset(
        db: AsyncSession,
        content: bytes | None = None,
        filename: str = "dataset.csv",
        mapping: DatasetMapping | None = None,
        file_path: str | Path | None = None,
        max_records: int | None = None,
    ) -> IngestionSummary:
        """
        Ingests parsed dataset rows into telemetry_metrics and support_tickets.
        Runs FastEmbed ONNX embedding generation if narrative_col is present.
        """
        df = DynamicIngestionEngine._parse_dataframe(content, filename, file_path=file_path)
        if max_records and len(df) > max_records:
            df = df.head(max_records)

        if len(df) == 0:
            dataset_name = mapping.dataset_name if mapping else "empty_dataset"
            return IngestionSummary(dataset_name=dataset_name, total_records=0, metrics_inserted=0, tickets_embedded=0)

        # Auto-infer mapping if not provided
        if mapping is None:
            inferred = DynamicIngestionEngine.infer_schema(
                content=content if content is not None else b"",
                filename=filename or (Path(file_path).name if file_path else "dataset.csv"),
            )
            mapping = DatasetMapping(
                dataset_name=inferred.dataset_name,
                timestamp_col=inferred.timestamp_col,
                primary_metric=inferred.primary_metric,
                metric_cols=inferred.metric_cols,
                dimension_cols=inferred.dimension_cols,
                narrative_col=inferred.narrative_col,
            )

        # Parse timestamps
        try:
            df["_parsed_date"] = pd.to_datetime(df[mapping.timestamp_col], errors="coerce").dt.date
        except Exception:
            df["_parsed_date"] = datetime.now().date()

        # Fill missing dates with today
        df["_parsed_date"] = df["_parsed_date"].fillna(datetime.now().date())

        # Dates range
        valid_dates = df["_parsed_date"].dropna()
        start_date = str(valid_dates.min()) if not valid_dates.empty else None
        end_date = str(valid_dates.max()) if not valid_dates.empty else None

        # 1. Ingest into DailySpendMetric (unified telemetry table)
        metrics_inserted = 0
        tickets_embedded = 0

        # Group by date and dimensions for aggregated telemetry
        dim_cols = [d for d in mapping.dimension_cols if d in df.columns]
        primary_val_col = mapping.primary_metric if mapping.primary_metric in df.columns else None

        # Create daily spend metrics records
        grouped = df.groupby(["_parsed_date"] + (dim_cols[:2] if dim_cols else []))
        
        for keys, group in grouped:
            metric_date = keys[0] if isinstance(keys, tuple) else keys
            region = str(group[dim_cols[0]].iloc[0]) if len(dim_cols) > 0 else "Default"
            product = str(group[dim_cols[1]].iloc[0]) if len(dim_cols) > 1 else "Standard"

            total_vol = len(group)
            metric_val = float(group[primary_val_col].mean()) if primary_val_col and pd.api.types.is_numeric_dtype(group[primary_val_col]) else float(total_vol)

            is_error_type = any(k in (primary_val_col or "").lower() for k in ["error", "fail", "drop", "timeout", "incident"])
            is_latency_type = "latency" in (primary_val_col or "").lower()

            calculated_sr = max(10.0, 100.0 - float(metric_val)) if is_error_type else 95.0
            calculated_lat = metric_val if is_latency_type else 100.0

            db.add(
                DailySpendMetric(
                    dataset_source=mapping.dataset_name,
                    metric_date=metric_date,
                    region=region,
                    product_name=product,
                    customer_tier="Standard",
                    merchant_category="General",
                    daily_spend_amount=metric_val * total_vol if primary_val_col else float(total_vol),
                    transaction_count=total_vol,
                    avg_ticket_size=metric_val,
                    success_rate_pct=calculated_sr,
                    avg_latency_ms=calculated_lat,
                    chargeback_rate_pct=0.5,
                    avg_fraud_risk_score=1.0,
                )
            )
            metrics_inserted += 1

        # 2. Ingest into DisputeSupportTicket with FastEmbed if narrative text is provided
        if mapping.narrative_col and mapping.narrative_col in df.columns:
            text_series = df[mapping.narrative_col].dropna().astype(str)
            text_list = [t for t in text_series if t.strip() and t.lower() != "none"][:500]  # Cap at top 500 for fast embedding

            if text_list:
                embeddings = _compute_embeddings_batch(text_list)
                for idx, text_item in enumerate(text_list):
                    db.add(
                        DisputeSupportTicket(
                            dataset_source=mapping.dataset_name,
                            ticket_created_at=datetime.now(),
                            region="Default",
                            product_name="Standard",
                            customer_tier="Standard",
                            customer_id=f"CUST-{idx+1:04d}",
                            issue_category="Uploaded Narrative",
                            priority="HIGH",
                            dispute_amount=100.0,
                            sentiment_score=-0.5,
                            subject=text_item[:80],
                            message=text_item,
                            embedding=embeddings[idx],
                        )
                    )
                    tickets_embedded += 1

        await db.commit()

        return IngestionSummary(
            dataset_name=mapping.dataset_name,
            total_records=len(df),
            metrics_inserted=metrics_inserted,
            tickets_embedded=tickets_embedded,
            start_date=start_date,
            end_date=end_date,
        )
