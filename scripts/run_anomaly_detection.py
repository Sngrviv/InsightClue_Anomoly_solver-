"""
Script to execute the AnomalyDetectionEngine over the seeded database.
Detects statistical & Isolation Forest anomalies and persists AnomalyEvents.
"""

import asyncio
import sys
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from src.database.session import AsyncSessionFactory, async_engine
from src.services.anomaly_detector import AnomalyDetectionEngine


async def run_detection():
    print("=" * 65)
    print("🔍 InsightClue: Running Statistical & ML Anomaly Detection Scan")
    print("=" * 65)

    engine = AnomalyDetectionEngine(
        rolling_window_days=14,
        z_score_threshold=2.5,
        isolation_forest_contamination=0.03,
    )

    async with AsyncSessionFactory() as session:
        # Clear previous anomaly events
        await session.execute(text("DELETE FROM investigation_reports;"))
        await session.execute(text("DELETE FROM anomaly_events;"))
        await session.commit()

        print("\n⏳ Scanning 21,840 Daily Spend records across all regions & products...")
        events = await engine.scan_and_persist(session=session)

        print(f"\n🎯 Detection Complete! Total Anomalies Discovered: {len(events)}")
        print("-" * 65)

        # Print detailed anomaly breakdown
        for i, ev in enumerate(events, 1):
            print(
                f"[{i:02d}] {ev.detected_at.date()} | {ev.severity:8s} | {ev.region:6s} | "
                f"{ev.product_name:24s} ({ev.customer_tier:10s}) | "
                f"Metric: {ev.metric_name} | "
                f"Actual: {ev.actual_value:.2f} (Exp: {ev.expected_value:.2f}, Dev: {ev.deviation_pct:+.1f}%, Z: {ev.z_score:.2f})"
            )

        print("-" * 65)
        critical_count = sum(1 for e in events if e.severity == "CRITICAL")
        print(f"📊 Summary: {critical_count} CRITICAL, {len(events) - critical_count} HIGH severity anomalies recorded.")
        print("✅ Ready for Phase 4 Multi-Agent AI Investigation!")

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_detection())
