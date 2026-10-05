"""
Deep Investigation Engine Seam for InsightClue.
Encapsulates LangGraph multi-agent orchestration, state lifecycle, and database persistence
behind a unified, high-leverage service interface.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncGenerator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.database.session import AsyncSessionFactory
from src.models.investigations import AnomalyEvent, InvestigationReport

logger = logging.getLogger(__name__)


class InvestigationService:
    """
    Deep module interface for autonomous Root Cause Analysis investigations.
    Hides graph compilation, state blackboard setup, reasoning trace extraction,
    and database persistence.
    """

    def __init__(self, graph_builder: InvestigationGraphBuilder | None = None) -> None:
        self.builder = graph_builder or InvestigationGraphBuilder()
        self.graph = self.builder.build_graph()

    def create_initial_state(
        self,
        anomaly: AnomalyEvent,
        trigger_source: str = "API_TRIGGER",
    ) -> InvestigationState:
        """Constructs standardized InvestigationState blackboard dictionary from an AnomalyEvent."""
        return {
            "anomaly_id": anomaly.id,
            "detected_at": anomaly.detected_at.isoformat() if anomaly.detected_at else datetime.now(timezone.utc).isoformat(),
            "region": anomaly.region,
            "product_name": anomaly.product_name,
            "customer_tier": anomaly.customer_tier,
            "metric_name": anomaly.metric_name,
            "actual_value": float(anomaly.actual_value),
            "expected_value": float(anomaly.expected_value),
            "deviation_pct": float(anomaly.deviation_pct),
            "z_score": float(anomaly.z_score),
            "severity": anomaly.severity,
            "trigger_source": trigger_source,
            "dataset_source": getattr(anomaly, "dataset_source", "KAGGLE_CFPB"),
            "active_hypothesis": f"Investigating {anomaly.metric_name} in {anomaly.region}.",
            "iteration_count": 0,
            "sql_history": [],
            "ticket_citations": [],
            "reasoning_trace": [],
            "root_cause_summary": "",
            "confidence_score": 0.0,
            "mitigation_steps": "",
            "is_complete": False,
        }

    async def run_investigation(
        self,
        anomaly_id: int,
        session: AsyncSession | None = None,
        trigger_source: str = "API_TRIGGER",
    ) -> InvestigationReport:
        """
        Executes the end-to-end multi-agent investigation squad for an anomaly and persists the final report.
        """
        if session is not None:
            return await self._execute_and_persist(anomaly_id, session, trigger_source)

        async with AsyncSessionFactory() as fresh_session:
            async with fresh_session.begin():
                return await self._execute_and_persist(anomaly_id, fresh_session, trigger_source)

    async def _execute_and_persist(
        self,
        anomaly_id: int,
        session: AsyncSession,
        trigger_source: str,
    ) -> InvestigationReport:
        """Internal execution helper with database persistence."""
        anomaly = await session.scalar(select(AnomalyEvent).where(AnomalyEvent.id == anomaly_id))
        if not anomaly:
            raise ValueError(f"Anomaly #{anomaly_id} not found.")

        # Check if already investigated
        existing_report = await session.scalar(
            select(InvestigationReport).where(InvestigationReport.anomaly_id == anomaly_id)
        )
        if existing_report:
            return existing_report

        anomaly.status = "INVESTIGATING"
        await session.flush()

        initial_state = self.create_initial_state(anomaly, trigger_source=trigger_source)
        final_state: InvestigationState = await self.graph.ainvoke(initial_state)

        # Update anomaly status
        anomaly.status = "RESOLVED"

        raw_rca = final_state.get("root_cause_summary", "Detailed RCA established.")
        rca_summary = "\n".join(raw_rca) if isinstance(raw_rca, list) else str(raw_rca)

        raw_mitigation = final_state.get("mitigation_steps", "1. Audit telemetry alerts.")
        mitigation = "\n".join(raw_mitigation) if isinstance(raw_mitigation, list) else str(raw_mitigation)

        # Create and persist finalized InvestigationReport
        report = InvestigationReport(
            anomaly_id=anomaly.id,
            generated_at=datetime.now(timezone.utc),
            root_cause_summary=rca_summary,
            confidence_score=float(final_state.get("confidence_score", 0.85)),
            evidence_data={
                "sql_history": final_state.get("sql_history", []),
                "ticket_citations": final_state.get("ticket_citations", []),
            },
            reasoning_trace=final_state.get("reasoning_trace", []),
            mitigation_steps=mitigation,
        )

        session.add(report)
        await session.flush()
        return report

    async def stream_investigation_events(
        self,
        anomaly_id: int,
        session: AsyncSession | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams live SSE agent thoughts and state transitions during multi-agent execution.
        """
        if session is not None:
            async for ev in self._stream_generator(anomaly_id, session):
                yield ev
            return

        async with AsyncSessionFactory() as fresh_session:
            async for ev in self._stream_generator(anomaly_id, fresh_session):
                yield ev

    async def _stream_generator(
        self,
        anomaly_id: int,
        session: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        anomaly = await session.scalar(select(AnomalyEvent).where(AnomalyEvent.id == anomaly_id))
        if not anomaly:
            yield f"event: error\ndata: {json.dumps({'error': f'Anomaly #{anomaly_id} not found'})}\n\n"
            return

        # Yield Anomaly Info
        yield (
            f"event: anomaly_info\n"
            f"data: {json.dumps({'id': anomaly.id, 'metric': anomaly.metric_name, 'region': anomaly.region, 'product': anomaly.product_name, 'severity': anomaly.severity, 'actual': anomaly.actual_value, 'expected': anomaly.expected_value})}\n\n"
        )

        initial_state = self.create_initial_state(anomaly, trigger_source="SSE_STREAM")

        async for chunk in self.graph.astream(initial_state):
            for node_name, node_state in chunk.items():
                for thought in node_state.get("reasoning_trace", []):
                    yield f"event: agent_thought\ndata: {json.dumps(thought)}\n\n"

                for sql in node_state.get("sql_history", []):
                    yield f"event: sql_evidence\ndata: {json.dumps(sql)}\n\n"

                for ticket in node_state.get("ticket_citations", []):
                    yield f"event: ticket_evidence\ndata: {json.dumps(ticket)}\n\n"

                if node_name == "synthesis_agent":
                    rca_payload = {
                        "root_cause_summary": node_state.get("root_cause_summary"),
                        "confidence_score": node_state.get("confidence_score"),
                        "mitigation_steps": node_state.get("mitigation_steps"),
                    }
                    yield f"event: rca_report\ndata: {json.dumps(rca_payload)}\n\n"

        # Persist report
        await self._execute_and_persist(anomaly_id, session, trigger_source="SSE_STREAM")
        await session.flush()
        yield f"event: complete\ndata: {json.dumps({'status': 'DONE', 'anomaly_id': anomaly_id})}\n\n"
