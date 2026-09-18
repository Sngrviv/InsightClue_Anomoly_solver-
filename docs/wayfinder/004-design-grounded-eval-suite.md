# 004 - Design Grounded Evaluation & Benchmark Harness

**Label**: `wayfinder:research`
**Status**: `open`
**Assignee**: `unassigned`
**Blocked by**: `003 - Simplify Multi-Agent Investigation Pipeline`

## Question

What evaluation methodology, dataset generation strategy, and scoring metrics should be used to benchmark InsightClue's end-to-end AI performance (RAG retrieval precision/recall, SQL investigation accuracy, and RCA synthesis correctness)?

Specifically:
1. What synthetic or ground-truth incident scenarios (e.g. gateway outage vs promotional spend surge) should constitute the golden benchmark test set?
2. How do we quantify precision, recall, latency, and token cost for agentic investigations?
3. How can this eval suite run as an automated test harness in CI/pytest?
