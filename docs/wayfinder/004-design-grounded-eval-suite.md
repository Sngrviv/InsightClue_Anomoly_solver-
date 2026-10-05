# 004 - Design Grounded Evaluation & Benchmark Harness

**Label**: `wayfinder:research`
**Status**: `closed`
**Assignee**: `Antigravity`
**Blocked by**: None

## Question

What evaluation methodology, dataset generation strategy, and scoring metrics should be used to benchmark InsightClue's end-to-end AI performance (RAG retrieval precision/recall, SQL investigation accuracy, and RCA synthesis correctness)?

Specifically:
1. What synthetic or ground-truth incident scenarios (e.g. gateway outage vs promotional spend surge) should constitute the golden benchmark test set?
2. How do we quantify precision, recall, latency, and token cost for agentic investigations?
3. How can this eval suite run as an automated test harness in CI/pytest?

## Resolution

1. **Multi-Domain Golden Benchmark Dataset**:
   - Established 3 ground-truth incident scenarios with annotated root causes and keyword expectations:
     - Scenario A: **CFPB Mortgage & Loan Disclosure Grievance Spike**
     - Scenario B: **Credit Card Billing Dispute & Unauthorized Surcharge Surge**
     - Scenario C: **Bank Account Transfer & Overdraft Latency Drift**
2. **Quantitative Scoring Metrics**:
   - **RAG Precision@K & Recall@K**: Verifying that retrieved tickets match the ground-truth issue category and keywords.
   - **SQL Proof Validity**: Verifying generated SQL queries execute without syntax violations and contain correct region/product filters.
   - **RCA Synthesis Faithfulness & Groundedness**: Ensuring generated report narratives strictly reflect observed SQL and RAG evidence without ungrounded hallucinations.
   - **Latency & Efficiency**: Tracking execution duration and graph iterations.
3. **Automated Evaluation Execution Seam**:
   - Automated Pytest integration in `tests/evals/test_investigation_evals.py`.
   - Standalone CLI Scoreboard in `scripts/run_evals.py` generating formatted markdown/terminal evaluation reports.
