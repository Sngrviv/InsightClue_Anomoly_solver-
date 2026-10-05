# Wayfinder Map: InsightClue AI Architecture Deepening & Mastery

**Label**: `wayfinder:map`

## Destination

Eliminate all shallow boilerplate, layer bloat, and AI slob from InsightClue by restructuring it into deep, highly testable modules with a grounded evaluation suite, establishing a production-grade AI Engineering system.

## Notes

- **Domain Glossary**: [CONTEXT.md](file:///d:/Projects/Self_learn/Major%20project/CONTEXT.md)
- **Primary Skills**: `codebase-design`, `grilling`, `domain-modeling`, `improve-codebase-architecture`
- **Architectural Principles**: Deep modules over shallow wrappers, "the interface is the test surface", high locality, strong seams, dynamic dataset generalization, and explicit async database session lifecycle.

## Decisions so far

- [001 - Deepen TicketVectorStore Interface & Encapsulation](file:///d:/Projects/Self_learn/Major%20project/docs/wayfinder/001-deepen-ticket-vector-store.md): Unified embedding generation, LRU query caching, and pgvector batch indexing inside `TicketVectorStore` behind `search()` and `index_tickets()` methods.
- [002 - Deepen AnomalyDetectionEngine Architecture](file:///d:/Projects/Self_learn/Major%20project/docs/wayfinder/002-deepen-anomaly-detection-engine.md): Streamlined `AnomalyDetectionEngine` with generalized multi-metric rolling statistical z-scores, continuous calendar gap-filling, Isolation Forest ensemble, and atomic DB deduplication.
- [003 - Simplify Multi-Agent Investigation Pipeline](file:///d:/Projects/Self_learn/Major%20project/docs/wayfinder/003-simplify-investigation-agent-pipeline.md): Central Supervisor blackboard topology in LangGraph with direct `SafeSQLSandbox` schema-aware querying, `TicketVectorStore` RAG retrieval, strict Pydantic report validation, and SSE observability.
- [004 - Design Grounded Evaluation & Benchmark Harness](file:///d:/Projects/Self_learn/Major%20project/docs/wayfinder/004-design-grounded-eval-suite.md): Established multi-domain golden benchmark incident scenarios, automated scoring harness for RAG Precision@K, SQL validity, and RCA faithfulness.
- [005 - Transactional Test Isolation Seam](file:///d:/Projects/Self_learn/Major%20project/docs/wayfinder/005-transactional-test-isolation-seam.md): Implemented nested savepoint rollback fixtures and deterministic test data injection in `tests/conftest.py`, guaranteeing zero test data pollution in live PostgreSQL tables.

## Frontier Tickets (Open & Unblocked)

All primary architecture roadmap tickets are resolved and closed!

## Blocked Tickets

None.

## Not yet specified

- **Production Observability & Tracing**: OpenTelemetry / Langfuse / custom spans for tracking token usage, latency, and agent trace graphs in real-time.
- **Dynamic Dataset Streaming & Batch Ingestion Seam**: Scalable async data ingestion for large CSVs/Parquet without in-memory spikes or intermediate DataFrame shallow wrappers.
- **Asynchronous Caching Invalidation Protocol**: High-concurrency Redis caching strategies for pgvector cosine queries and rolling metric aggregations.

## Out of scope

- Generic frontend UI redesign (focus is strictly on backend systems architecture, pgvector, Redis, and multi-agent AI orchestration).
- Multi-cloud Kubernetes orchestration / Helm charts (constrained to local Docker Compose and production Python environments).
- Proprietary closed-source vector DB SaaS migrations (Pinecone/Weaviate; system uses PostgreSQL + pgvector).
