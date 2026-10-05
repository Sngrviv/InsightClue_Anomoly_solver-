# 003 - Simplify Multi-Agent Investigation Pipeline

**Label**: `wayfinder:grilling`
**Status**: `closed`
**Assignee**: `Antigravity`
**Blocked by**: None

## Question

How should the Root Cause Analysis (RCA) multi-agent investigation workflow (`investigation_graph.py`, `llm_client.py`, and tool dispatch) be streamlined into an observable, robust agentic seam without shallow boilerplate or fragile prompt chains?

Specifically:
1. What state schema cleanly carries the anomaly context, SQL proofs, and RAG ticket citations without leaking graph internals?
2. How should LLM tool-calling directly invoke the deep domain modules (`TicketVectorStore`, SQL query engine) without intermediate adapter layers?
3. How do we ensure deterministic fallback, timeout handling, and structured Pydantic report validation?

## Resolution

1. **Central Supervisor Blackboard Topology**:
   - `InvestigationState` TypedDict acts as the single source of truth across the graph with append reducers for `sql_history`, `ticket_citations`, and `reasoning_trace`.
   - Supervisor (Lead Detective) dynamically routes between `sql_agent` (quantitative telemetry proofs) and `rag_agent` (qualitative customer dispute grievances) until evidence from both is collected or max iterations (4) are reached, transitioning directly to `synthesis_agent`.
2. **Direct Seam Tool Dispatch**:
   - `sql_agent` directly invokes `SafeSQLSandbox` with runtime schema introspection (`get_schema_summary()`) and AST/Regex read-only query sanitation.
   - `rag_agent` directly invokes `TicketVectorStore` with LRU query caching and pgvector cosine distance lookups.
3. **Structured Validation & Resilience**:
   - Final report is validated against a strict Pydantic model (`InvestigationReport`) with bounded confidence scores (0.0-1.0), structured mitigations, and citation links.
   - Real-time SSE event streaming (`thought`, `sql_query`, `rag_citations`, `final_report`, `complete`) enables complete runtime observability.
   - Dynamic contextual fallbacks ensure deterministic operation even during external LLM API timeouts.
