# InsightClue Domain Context & Architecture Dictionary

## Domain Concepts
- **`DailySpendMetric`**: Daily aggregated financial transaction volume, spend amount, success rate %, average latency, and chargeback % partitioned by Region, Product, Tier, and Category.
- **`PaymentGatewayLog`**: Technical banking partner infrastructure logs tracking HTTP 504 timeouts, HTTP 500 error rates, response latencies, and switch availability states (`OPERATIONAL`, `DEGRADED`, `OUTAGE`).
- **`DisputeSupportTicket`**: Unstructured customer complaints, dispute escalations, sentiment scores, and 768-dimensional semantic embeddings.
- **`AnomalyEvent`**: An automated detection signal flagged when metric values deviate significantly from statistical/ML baseline models.
- **`InvestigationReport`**: Synthesized multi-agent Root Cause Analysis report with structured SQL proof, RAG ticket citations, and recommended mitigation steps.

## Architectural Seams & Modules
- **`TicketVectorStore`**: Deep vector storage and semantic search module. Hides embedding generation, vector distance operators (`<=>`), threshold filtering, and ORM object hydration behind a narrow query interface.
- **`AnomalyDetectionEngine`**: Deep statistical and ML anomaly detection seam. Encapsulates rolling baselines, feature normalization, Isolation Forest modeling, and severity scoring.
