# 0001: Unified Partitioned Ingestion with Dynamic Schema Inference

## Context
InsightClue previously hardcoded the Kaggle CFPB complaint schema across the ingestion adapter and multi-agent graph. To support arbitrary user-uploaded datasets (e.g. payment logs, server metrics, customer support churn) without changing backend code, we needed an ingestion and querying architecture that can handle heterogeneous columns while preserving relational indexing and vector search performance.

## Decision
We chose a **Unified Partitioned Storage Model** over dynamic DDL table creation. All ingested datasets are normalized and written into existing `telemetry_metrics` and `support_tickets` tables with an indexed `dataset_name` partition key. 

On upload:
1. An inference engine inspects the first 100 rows and maps columns to 4 semantic roles: `timestamp`, `primary_metric`, `dimension_keys`, and optional `narrative_text`.
2. Telemetry and time-series data are stored with generic metric values and JSONB/relational dimensions.
3. If a qualitative text column is present, `FastEmbed` generates 768-dim $L_2$-normalized embeddings stored in `pgvector`. If absent, the multi-agent investigation squad gracefully adapts to pure quantitative SQL analysis.
4. `InvestigationState` is dynamically injected with the active dataset's schema metadata so `SqlAnalystAgent` generates valid queries for any arbitrary dataset.

## Status
Accepted
