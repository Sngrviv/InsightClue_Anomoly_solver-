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

from src.models.investigations import AnomalyEvent
from src.services.investigation_service import InvestigationService


async def run_evaluation_suite():
    print("=" * 70, flush=True)
    print("🏆 InsightClue AI Engineering Evaluation & Benchmark Harness", flush=True)
    print("=" * 70, flush=True)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", flush=True)
    print(f"Total Benchmark Scenarios: {len(GOLDEN_BENCHMARKS)}\n", flush=True)

    service = InvestigationService()
    results = []

    for scenario in GOLDEN_BENCHMARKS:
        print(f"▶️  Running [{scenario['id']}] {scenario['title']}...", flush=True)
        start_t = time.perf_counter()

        dummy_anomaly = AnomalyEvent(
            id=scenario["anomaly"]["anomaly_id"],
            detected_at=datetime.now(timezone.utc),
            region=scenario["anomaly"]["region"],
            product_name=scenario["anomaly"]["product_name"],
            customer_tier=scenario["anomaly"]["customer_tier"],
            metric_name=scenario["anomaly"]["metric_name"],
            actual_value=scenario["anomaly"]["actual_value"],
            expected_value=scenario["anomaly"]["expected_value"],
            deviation_pct=scenario["anomaly"]["deviation_pct"],
            z_score=scenario["anomaly"]["z_score"],
            severity=scenario["anomaly"]["severity"],
            status="OPEN",
        )
        setattr(dummy_anomaly, "dataset_source", scenario["anomaly"]["dataset_source"])

        initial_state = service.create_initial_state(dummy_anomaly, trigger_source="BENCHMARK")

        try:
            final_state = await service.graph.ainvoke(initial_state)
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
