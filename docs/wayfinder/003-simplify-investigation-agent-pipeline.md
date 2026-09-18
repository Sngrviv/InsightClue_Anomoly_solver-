# 003 - Simplify Multi-Agent Investigation Pipeline

**Label**: `wayfinder:grilling`
**Status**: `open`
**Assignee**: `unassigned`
**Blocked by**: `001 - Deepen TicketVectorStore Interface & Encapsulation`, `002 - Deepen AnomalyDetectionEngine Architecture`

## Question

How should the Root Cause Analysis (RCA) multi-agent investigation workflow (`investigation_graph.py`, `llm_client.py`, and tool dispatch) be streamlined into an observable, robust agentic seam without shallow boilerplate or fragile prompt chains?

Specifically:
1. What state schema cleanly carries the anomaly context, SQL proofs, and RAG ticket citations without leaking graph internals?
2. How should LLM tool-calling directly invoke the deep domain modules (`TicketVectorStore`, SQL query engine) without intermediate adapter layers?
3. How do we ensure deterministic fallback, timeout handling, and structured Pydantic report validation?
