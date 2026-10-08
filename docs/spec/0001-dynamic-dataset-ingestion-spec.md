# Specification: Universal Dynamic Dataset Ingestion & Adaptive Multi-Agent Engine

## Problem Statement
InsightClue was initially designed with hardcoded column references tailored solely to the Kaggle CFPB complaints dataset. Real users require an autonomous anomaly detection and root cause analysis engine that can accept heterogeneous datasets across multiple domains (e.g., payment transaction logs, cloud microservice latencies, IT helpdesk tickets, IoT sensor metrics) without requiring code modifications, manual schema migrations, or restarts.

## Solution
Introduce a deep `DynamicIngestionEngine` module and a multi-format upload seam (`/api/datasets/upload`) that:
1. Accepts `.csv`, `.json`, `.sqlite`, and `.parquet` files via the Mission Control UI.
2. Performs fast heuristic and statistical schema inference over sample rows to identify semantic roles (`timestamp`, `primary_metric`, `dimension_keys`, optional `narrative_text`).
3. Bulk-ingests normalized metrics and ticket vectors into indexed PostgreSQL partitions tagged by `dataset_name`.
4. Enables the LangGraph Multi-Agent squad (`SupervisorAgent`, `SqlAnalystAgent`, `SupportVectorAgent`, `SynthesizerAgent`) to dynamically receive active schema metadata in `InvestigationState` and autonomously analyze any uploaded dataset.

## User Stories

1. As a FinTech Data Engineer, I want to upload a CSV of payment gateway logs through the frontend dashboard, so that I can analyze transaction failure spikes without configuring database tables.
2. As a DevOps SRE, I want to upload cloud latency metrics in JSON format, so that I can detect API response degradation across service regions.
3. As an Analyst, I want the system to automatically infer which column represents time/date, so that I don't have to manually format timestamps before uploading.
4. As an Analyst, I want the system to suggest the primary numerical metric and categorical dimensions, so that I can confirm or tweak column mappings before ingestion begins.
5. As an Analyst, I want to upload pure numerical telemetry without customer complaint narratives, so that the anomaly detection and SQL analytics agents run smoothly even when qualitative text is absent.
6. As a Security Officer, I want customer complaint narratives to be vectorized locally on CPU using FastEmbed ONNX, so that sensitive customer data is never sent to third-party embedding APIs.
7. As a User, I want to switch between multiple uploaded datasets using a dropdown in the UI header, so that I can compare anomaly patterns across different environments.
8. As a System Administrator, I want large datasets (up to 100,000 rows) to ingest in streaming batches using asyncpg, so that the FastAPI web server remains responsive during ingestion.
9. As a Lead Detective (Supervisor Agent), I want to receive the active dataset's column mappings in the blackboard state, so that I can generate relevant investigation hypotheses.
10. As a SQL Analyst Agent, I want to dynamically query the active dataset's partition columns using read-only AST-validated SQL, so that I can verify quantitative metrics on any arbitrary schema.
11. As an RCA Synthesizer Agent, I want to adaptively generate Root Cause reports based on available quantitative and qualitative evidence, so that investigations are always grounded in verified facts.

## Implementation Decisions

1. **Unified Partitioned Storage Model**:
   - Store all uploaded data in existing PostgreSQL tables (`telemetry_metrics` and `support_tickets`) using an indexed `dataset_name` discriminator column.
   - Avoid runtime DDL operations (`CREATE TABLE`) to maintain clean ORM consistency and connection pool stability.

2. **Dynamic Schema Inference Contract**:
   - `DynamicIngestionEngine.infer_schema(file_bytes, filename)` returns:
     ```json
     {
       "dataset_name": "payments_prod",
       "timestamp_col": "created_at",
       "metric_cols": ["latency_ms", "error_count"],
       "primary_metric": "latency_ms",
       "dimension_cols": ["gateway", "status", "region"],
       "narrative_col": "error_log"
     }
     ```

3. **Multi-Format Ingestion Adapter**:
   - Support `.csv` (via `pandas.read_csv`), `.json` (via `pandas.read_json`), and `.sqlite` (via `sqlite3`/`pandas`).
   - Normalizes parsed records into `telemetry_metrics` rows with `timestamp`, `metric_value`, `dataset_name`, and dimensions.

4. **Optional FastEmbed ONNX Vector Indexing**:
   - If `narrative_col` is provided, generate 768-dim $L_2$-normalized vectors in batches of 128 and write to `support_tickets`.
   - If `narrative_col` is `None`, skip vector generation; `TicketVectorStore` returns empty results gracefully.

5. **Investigation State Dynamic Injection**:
   - `InvestigationService.run_investigation()` queries dataset metadata and injects `dataset_schema` into `InvestigationState` before compiling LangGraph.

6. **API Endpoints**:
   - `POST /api/datasets/upload`: Accepts multipart form file upload, returns inferred schema.
   - `POST /api/datasets/confirm-ingestion`: Accepts confirmed mapping and executes chunked database write.
   - `GET /api/datasets`: Lists all active datasets with record counts and date ranges.

## Testing Decisions

- **Test Seam**: High-level service and API contract testing against real PostgreSQL 16 + pgvector container (with transactional rollback in `tests/conftest.py`).
- **Unit Tests**:
  - Test schema inference on diverse mock files (pure numerical, mixed text/numerical, non-standard timestamps).
  - Test bulk chunked ingestion into `telemetry_metrics` and `support_tickets`.
  - Test `TelemetryMetricStore` and `AnomalyDetector` executing against non-CFPB custom datasets.
  - Test `InvestigationService` and LangGraph multi-agent flow with custom dataset metadata.
- **Prior Art**: Follow the deep module pattern in `tests/test_telemetry_store.py` and `tests/test_investigation_service.py`.

## Out of Scope

- Multi-tenant user authentication and RBAC permissions (kept single-workspace for local mission control).
- Real-time Kafka / Kinesis streaming ingestion (batch file uploads are prioritized).

## Further Notes
The dynamic ingestion engine preserves 100% backward compatibility with existing Kaggle CFPB complaint records while unlocking universal anomaly detection across any structured tabular domain.
