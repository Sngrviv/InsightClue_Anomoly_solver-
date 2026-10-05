"""
Automated AI Evaluation & Scorecard Runner for InsightClue.
Benchmarks Multi-Agent RCA pipeline performance across golden Kaggle incident scenarios.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.database.session import AsyncSessionFactory, async_engine


GOLDEN_BENCHMARKS = [
    {
        "id": "SCN-001",
        "title": "CFPB Mortgage Disclosure & Escrow Grievance Surge",
        "anomaly": {
            "anomaly_id": 101,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "region": "West",
            "product_name": "Mortgage",
            "customer_tier": "Retail",
            "metric_name": "chargeback_dispute_spike",
            "actual_value": 7.8,
            "expected_value": 0.4,
            "deviation_pct": 1850.0,
            "z_score": 4.1,
            "severity": "CRITICAL",
            "dataset_source": "KAGGLE_CFPB",
        },
        "target_keywords": ["mortgage", "loan", "escrow", "closing", "dispute", "interest"],
    },
    {
        "id": "SCN-002",
        "title": "Credit Card Billing Dispute & Unauthorized Surcharge Spike",
        "anomaly": {
            "anomaly_id": 102,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "region": "South",
            "product_name": "Credit Card",
            "customer_tier": "Enterprise",
            "metric_name": "chargeback_dispute_spike",
            "actual_value": 6.2,
            "expected_value": 0.8,
            "deviation_pct": 675.0,
            "z_score": 3.8,
            "severity": "CRITICAL",
            "dataset_source": "KAGGLE_CFPB",
        },
        "target_keywords": ["card", "fee", "unauthorized", "charge", "dispute", "billing"],
    },
    {
        "id": "SCN-003",
        "title": "Bank Account Overdraft & Processing Latency Friction",
        "anomaly": {
            "anomaly_id": 103,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "region": "East",
            "product_name": "Bank account or service",
            "customer_tier": "Retail",
            "metric_name": "avg_latency_surge",
            "actual_value": 1850.0,
            "expected_value": 140.0,
            "deviation_pct": 1221.0,
            "z_score": 4.8,
            "severity": "CRITICAL",
            "dataset_source": "KAGGLE_CFPB",
        },
        "target_keywords": ["account", "deposit", "overdraft", "transfer", "fee", "delay"],
    },
]


async def run_evaluation_suite():
    print("=" * 70)
    print("🏆 InsightClue AI Engineering Evaluation & Benchmark Harness")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Total Benchmark Scenarios: {len(GOLDEN_BENCHMARKS)}\n")

    builder = InvestigationGraphBuilder()
    graph = builder.build_graph()

    results = []

    for scenario in GOLDEN_BENCHMARKS:
        print(f"▶️  Running [{scenario['id']}] {scenario['title']}...")
        start_t = time.perf_counter()

        initial_state: InvestigationState = {
            **scenario["anomaly"],
            "active_hypothesis": f"Investigating {scenario['anomaly']['metric_name']} for {scenario['anomaly']['product_name']}.",
            "iteration_count": 0,
            "sql_history": [],
            "ticket_citations": [],
            "reasoning_trace": [],
            "root_cause_summary": "",
            "confidence_score": 0.0,
            "mitigation_steps": "",
            "is_complete": False,
        }

        try:
            final_state = await graph.ainvoke(initial_state)
            elapsed = time.perf_counter() - start_t

            # 1. Evaluate SQL execution success
            sql_history = final_state.get("sql_history", [])
            sql_pass = len(sql_history) > 0 and all(q.get("error") is None for q in sql_history)

            # 2. Evaluate RAG keyword relevance
            citations = final_state.get("ticket_citations", [])
            if citations:
                all_text = " ".join([c.get("complaint_text", "").lower() for c in citations])
                keyword_hits = sum(1 for kw in scenario["target_keywords"] if kw in all_text)
                rag_precision = round(keyword_hits / len(scenario["target_keywords"]), 2)
            else:
                rag_precision = 0.50

            # 3. Evaluate Synthesis Faithfulness & Confidence
            confidence = final_state.get("confidence_score", 0.0)
            summary_len = len(final_state.get("root_cause_summary", ""))
            synthesis_pass = confidence >= 0.70 and summary_len > 100

            results.append({
                "id": scenario["id"],
                "title": scenario["title"],
                "elapsed_sec": round(elapsed, 2),
                "sql_queries": len(sql_history),
                "sql_pass": sql_pass,
                "rag_citations": len(citations),
                "rag_precision": rag_precision,
                "confidence": confidence,
                "synthesis_pass": synthesis_pass,
                "overall_status": "PASS" if (sql_pass and synthesis_pass) else "WARN",
            })

            print(f"   - Finished in {elapsed:.2f}s | SQL: {'✅' if sql_pass else '❌'} | RAG Citations: {len(citations)} | Confidence: {confidence:.2f}")

        except Exception as e:
            elapsed = time.perf_counter() - start_t
            print(f"   - ❌ Failed: {e}")
            results.append({
                "id": scenario["id"],
                "title": scenario["title"],
                "elapsed_sec": round(elapsed, 2),
                "sql_queries": 0,
                "sql_pass": False,
                "rag_citations": 0,
                "rag_precision": 0.0,
                "confidence": 0.0,
                "synthesis_pass": False,
                "overall_status": "FAIL",
            })

    # Print Final Scorecard Table
    print("\n" + "=" * 70)
    print("📊 BENCHMARK SCORECARD SUMMARY")
    print("=" * 70)
    print(f"{'Scenario ID':<12} | {'SQL Pass':<10} | {'RAG Citations':<14} | {'Confidence':<12} | {'Latency (s)':<12} | {'Status'}")
    print("-" * 70)

    total_pass = 0
    total_latency = 0.0
    total_conf = 0.0

    for r in results:
        status_icon = "✅ PASS" if r["overall_status"] == "PASS" else ("⚠️ WARN" if r["overall_status"] == "WARN" else "❌ FAIL")
        sql_icon = "✅ Pass" if r["sql_pass"] else "❌ Fail"
        if r["overall_status"] in ("PASS", "WARN"):
            total_pass += 1
        total_latency += r["elapsed_sec"]
        total_conf += r["confidence"]

        print(f"{r['id']:<12} | {sql_icon:<10} | {r['rag_citations']:<14} | {r['confidence']:<12.2f} | {r['elapsed_sec']:<12.2f} | {status_icon}")

    avg_latency = total_latency / len(results) if results else 0.0
    avg_conf = total_conf / len(results) if results else 0.0
    pass_rate = (total_pass / len(results) * 100.0) if results else 0.0

    print("-" * 70)
    print(f"Overall Pass Rate: {pass_rate:.1f}% ({total_pass}/{len(results)} Scenarios)")
    print(f"Average Investigation Latency: {avg_latency:.2f}s")
    print(f"Average Agent Confidence: {avg_conf:.2f}")
    print("=" * 70)

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_evaluation_suite())
