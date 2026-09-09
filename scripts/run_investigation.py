"""
End-to-End Autonomous Multi-Agent Investigation Driver.
Picks an open AnomalyEvent from PostgreSQL, orchestrates the LangGraph squad,
streams live agent reasoning traces, persists the InvestigationReport, and saves reports/rca_<id>.md.
"""

import asyncio
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.database.session import AsyncSessionFactory
from src.models.investigations import AnomalyEvent, InvestigationReport


async def run_investigation_for_anomaly(
    anomaly_id: int | None = None,
    session: AsyncSession | None = None,
) -> dict[str, str]:
    """
    Runs the multi-agent investigation workflow for a specific or next open anomaly.
    """
    async with AsyncSessionFactory() as db:
        if anomaly_id is not None:
            stmt = select(AnomalyEvent).where(AnomalyEvent.id == anomaly_id)
        else:
            # Pick highest severity open anomaly
            stmt = (
                select(AnomalyEvent)
                .where(AnomalyEvent.status == "OPEN")
                .order_by(AnomalyEvent.severity.desc(), AnomalyEvent.detected_at.desc())
                .limit(1)
            )

        result = await db.execute(stmt)
        anomaly = result.scalar_one_or_none()

        if not anomaly:
            print("No open anomaly events found to investigate.")
            return {"status": "NO_ANOMALY_FOUND"}

        print("\n=======================================================")
        print("[*] INSIGHTCLUE MULTI-AGENT SQUAD DISPATCHED")
        print("=======================================================")
        print(f"Anomaly ID     : #{anomaly.id}")
        print(f"Metric Flagged : {anomaly.metric_name}")
        print(f"Segment        : {anomaly.region} | {anomaly.product_name} | {anomaly.customer_tier}")
        print(f"Actual Value   : {anomaly.actual_value:.2f}% (Expected: {anomaly.expected_value:.2f}%)")
        print(f"Deviation      : {anomaly.deviation_pct:.2f}% (Z-Score: {anomaly.z_score:.2f})")
        print(f"Severity       : {anomaly.severity}")
        print(f"=======================================================\n")

        # Mark anomaly as INVESTIGATING
        anomaly.status = "INVESTIGATING"
        await db.commit()

        # Build initial LangGraph State
        initial_state: InvestigationState = {
            "anomaly_id": anomaly.id,
            "detected_at": anomaly.detected_at.isoformat(),
            "region": anomaly.region,
            "product_name": anomaly.product_name,
            "customer_tier": anomaly.customer_tier,
            "metric_name": anomaly.metric_name,
            "actual_value": anomaly.actual_value,
            "expected_value": anomaly.expected_value,
            "deviation_pct": anomaly.deviation_pct,
            "z_score": anomaly.z_score,
            "severity": anomaly.severity,
            "trigger_source": "METRIC_SCAN",
            "active_hypothesis": f"Investigating {anomaly.metric_name} in {anomaly.region} on {anomaly.product_name}.",
            "iteration_count": 0,
            "sql_history": [],
            "ticket_citations": [],
            "reasoning_trace": [],
        }

        # Compile and run LangGraph
        graph_builder = InvestigationGraphBuilder()
        workflow = graph_builder.build_graph()

        final_state = await workflow.ainvoke(initial_state)

        # Print live reasoning traces
        print("[*] AGENT THOUGHT TRACES & EVIDENCE GATHERING:")
        print("-------------------------------------------------------")
        for step in final_state.get("reasoning_trace", []):
            print(f"[{step['agent']}] -> {step['thought']}")

        print("\n=======================================================")
        print("[*] FINAL ROOT CAUSE ANALYSIS (RCA) VERDICT")
        print("=======================================================")
        print(f"Confidence Score : {final_state.get('confidence_score', 0.95) * 100:.1f}%")
        print(f"\nRoot Cause Summary:\n{final_state.get('root_cause_summary')}")
        print(f"\nRecommended Mitigations:\n{final_state.get('mitigation_steps')}")
        print("=======================================================\n")

        # Persist InvestigationReport to PostgreSQL
        report = InvestigationReport(
            anomaly_id=anomaly.id,
            generated_at=datetime.now(timezone.utc),
            root_cause_summary=final_state.get("root_cause_summary", "RCA completed."),
            confidence_score=float(final_state.get("confidence_score", 0.95)),
            evidence_data={
                "sql_history": final_state.get("sql_history", []),
                "ticket_citations": final_state.get("ticket_citations", []),
            },
            reasoning_trace=final_state.get("reasoning_trace", []),
            mitigation_steps=final_state.get("mitigation_steps", "Apply remediations."),
        )

        db.add(report)
        anomaly.status = "RESOLVED"
        await db.commit()

        # Save Markdown Report in reports/
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"rca_{anomaly.id}.md"

        markdown_content = f"""# 🔍 Executive Root Cause Analysis (RCA) Report

- **Incident ID**: `anom_{anomaly.id}`
- **Generated At**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Target Segment**: `{anomaly.region}` | `{anomaly.product_name}` | `{anomaly.customer_tier}`
- **Metric Anomaly**: `{anomaly.metric_name}` (Actual: **{anomaly.actual_value:.2f}%**, Expected: **{anomaly.expected_value:.2f}%**, Deviation: **{anomaly.deviation_pct:.2f}%**)
- **Severity**: `{anomaly.severity}`
- **Confidence Score**: **{final_state.get('confidence_score', 0.95) * 100:.1f}%**

---

## 📌 Executive Summary
{final_state.get('root_cause_summary')}

---

## 🛠️ Recommended Action & Mitigation Plan
{final_state.get('mitigation_steps')}

---

## 📊 Technical Evidence (SQL Analytics Agent)
"""
        for q in final_state.get("sql_history", []):
            markdown_content += f"""
```sql
{q['query']}
```
- **Rows Matched**: {q['row_count']}
- **Explanation**: {q['explanation']}
"""

        markdown_content += "\n---\n\n## 💬 Customer Support Citations (Vector RAG Agent)\n"
        for t in final_state.get("ticket_citations", []):
            markdown_content += f"""- **Ticket #{t['ticket_id']}** (Similarity: `{t['similarity_score']:.2f}`): *"{t['complaint_text']}"*\n"""

        markdown_content += "\n---\n\n## 🧠 Multi-Agent Reasoning Trace\n"
        for trace in final_state.get("reasoning_trace", []):
            markdown_content += f"- **[{trace['agent']}]**: {trace['thought']}\n"

        report_path.write_text(markdown_content, encoding="utf-8")
        print(f"[+] Report persisted to PostgreSQL & written to {report_path.resolve()}")

        return {
            "status": "SUCCESS",
            "anomaly_id": str(anomaly.id),
            "report_file": str(report_path),
        }


if __name__ == "__main__":
    asyncio.run(run_investigation_for_anomaly())
