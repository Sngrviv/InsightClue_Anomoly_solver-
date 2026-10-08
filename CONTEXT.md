# InsightClue Domain Context & Architecture Dictionary

## Domain Concepts
- **`DailySpendMetric`**: Daily aggregated financial transaction volume, spend amount, success rate %, average latency, and chargeback % partitioned by Region, Product, Tier, and Category.
- **`PaymentGatewayLog`**: Technical banking partner infrastructure logs tracking HTTP 504 timeouts, HTTP 500 error rates, response latencies, and switch availability states (`OPERATIONAL`, `DEGRADED`, `OUTAGE`).
- **`DisputeSupportTicket`**: Unstructured customer complaints, dispute escalations, sentiment scores, and 768-dimensional semantic embeddings.
- **`AnomalyEvent`**: An automated detection signal flagged when metric values deviate significantly from statistical/ML baseline models.
- **`InvestigationReport`**: Synthesized multi-agent Root Cause Analysis report with structured SQL proof, RAG ticket citations, and recommended mitigation steps.
- **`DatasetPartition`**: Isolated logical partition representing an uploaded or seeded dataset with associated metadata (dataset name, record count, detected date range, primary target metric).
- **`DatasetSchemaMapping`**: Semantic mapping of arbitrary input file columns to analytical roles (`timestamp`, `primary_metric`, `dimension_keys`, `narrative_text`).

## Architectural Seams & Modules
- **`TelemetryMetricStore`**: Deep telemetry storage and aggregation seam. Encapsulates SQL aggregations (`func.sum`, `func.avg`, date groupings), zero-division guards, and multi-table KPI synthesis away from API routes.
- **`DynamicIngestionEngine`**: Deep ingestion and schema inference module that parses arbitrary multi-format files (CSV, JSON, SQLite, Parquet), runs type and heuristic role inference, generates batch FastEmbed embeddings, and commits partitioned records to PostgreSQL.
- **`TicketVectorStore`**: Deep vector storage and semantic search module. Hides embedding generation, vector distance operators (`<=>`), threshold filtering, and ORM object hydration behind a narrow query interface.
- **`AnomalyDetectionEngine`**: Deep statistical and ML anomaly detection seam. Encapsulates rolling baselines, feature normalization, Isolation Forest modeling, and severity scoring.
- **`InvestigationService`**: Central multi-agent Root Cause Analysis orchestration seam. Hides LangGraph graph compilation, blackboard state lifecycle, Server-Sent Events (SSE) streaming, dynamic schema injection, and atomic database persistence.
- **`LLMClient`**: Non-blocking asynchronous AI gateway with multi-model candidate cascading (`gemini-3.1-flash-lite`, `gemini-flash-lite-latest`, `gemini-3.5-flash-lite`) and structured JSON schema validation.
