"""
Unit and integration tests for the deep InvestigationService seam.
Verifies blackboard state construction, multi-agent invocation, atomic report persistence,
and real-time SSE event streaming.
"""

import json
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.investigations import AnomalyEvent, InvestigationReport
from src.services.investigation_service import InvestigationService


@pytest.mark.asyncio
async def test_investigation_service_create_initial_state(seeded_db_session: AsyncSession):
    service = InvestigationService()
    anomaly = await seeded_db_session.scalar(select(AnomalyEvent).limit(1))
    assert anomaly is not None

    state = service.create_initial_state(anomaly, trigger_source="TEST_SUITE")
    assert state["anomaly_id"] == anomaly.id
    assert state["region"] == anomaly.region
    assert state["product_name"] == anomaly.product_name
    assert state["metric_name"] == anomaly.metric_name
    assert state["trigger_source"] == "TEST_SUITE"
    assert state["iteration_count"] == 0
    assert state["sql_history"] == []
    assert state["ticket_citations"] == []
    assert state["reasoning_trace"] == []
    assert state["is_complete"] is False


@pytest.mark.asyncio
async def test_investigation_service_run_investigation(seeded_db_session: AsyncSession):
    service = InvestigationService()
    anomaly = await seeded_db_session.scalar(
        select(AnomalyEvent).where(AnomalyEvent.status == "OPEN").limit(1)
    )
    assert anomaly is not None

    report = await service.run_investigation(anomaly_id=anomaly.id, session=seeded_db_session)
    assert isinstance(report, InvestigationReport)
    assert report.anomaly_id == anomaly.id
    assert len(report.root_cause_summary) > 0
    assert 0.0 <= report.confidence_score <= 1.0
    assert len(report.mitigation_steps) > 0
    assert anomaly.status == "RESOLVED"

    # Idempotency check: running again on resolved anomaly returns existing report
    report_second = await service.run_investigation(anomaly_id=anomaly.id, session=seeded_db_session)
    assert report_second.id == report.id


@pytest.mark.asyncio
async def test_investigation_service_stream_events(seeded_db_session: AsyncSession):
    service = InvestigationService()
    anomaly = await seeded_db_session.scalar(
        select(AnomalyEvent).where(AnomalyEvent.status == "OPEN").limit(1)
    )
    assert anomaly is not None

    events = []
    async for raw_event in service.stream_investigation_events(anomaly_id=anomaly.id, session=seeded_db_session):
        lines = [l.strip() for l in raw_event.split("\n") if l.strip()]
        for line in lines:
            if line.startswith("event:"):
                events.append(line.replace("event:", "").strip())

    assert len(events) > 0
    assert "anomaly_info" in events
    assert "complete" in events
