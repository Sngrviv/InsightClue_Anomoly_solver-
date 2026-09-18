"""
Multi-Agent RCA investigation execution and real-time SSE streaming routes.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.api.schemas.investigation import (
    InvestigationReportDetailResponse,
    InvestigationTriggerResponse,
)
from src.database.session import AsyncSessionFactory, get_db
from src.models.investigations import AnomalyEvent, InvestigationReport

router = APIRouter(prefix="/investigations", tags=["Multi-Agent Investigations"])


@router.get("/reports/{anomaly_id}", response_model=InvestigationReportDetailResponse)
async def get_investigation_report(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
) -> InvestigationReportDetailResponse:
    """
    Retrieves the complete synthesized RCA report with all SQL queries and ticket citations.
    """
    stmt = select(InvestigationReport).where(InvestigationReport.anomaly_id == anomaly_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation report for Anomaly #{anomaly_id} not found.",
        )

    return InvestigationReportDetailResponse.model_validate(report)


@router.post("/trigger/{anomaly_id}", response_model=InvestigationTriggerResponse)
async def trigger_investigation(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
) -> InvestigationTriggerResponse:
    """
    Synchronously triggers the LangGraph multi-agent investigation squad for an anomaly.
    """
    stmt = select(AnomalyEvent).where(AnomalyEvent.id == anomaly_id)
    result = await db.execute(stmt)
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly #{anomaly_id} not found.",
        )

    # If already resolved and report exists, return existing status
    existing_report = await db.scalar(
        select(InvestigationReport).where(InvestigationReport.anomaly_id == anomaly_id)
    )
    if existing_report:
        return InvestigationTriggerResponse(
            status="ALREADY_RESOLVED",
            anomaly_id=anomaly.id,
            message="Investigation report already exists for this anomaly.",
        )

    anomaly.status = "INVESTIGATING"
    await db.commit()

    # Build LangGraph state
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
        "trigger_source": "API_TRIGGER",
        "dataset_source": getattr(anomaly, "dataset_source", "FINTECH_90D"),
        "active_hypothesis": f"Investigating {anomaly.metric_name} in {anomaly.region}.",
        "iteration_count": 0,
        "sql_history": [],
        "ticket_citations": [],
        "reasoning_trace": [],
    }

    graph_builder = InvestigationGraphBuilder()
    workflow = graph_builder.build_graph()
    final_state = await workflow.ainvoke(initial_state)

    # Persist report
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
        mitigation_steps=final_state.get("mitigation_steps", "Apply mitigations."),
    )
    db.add(report)
    anomaly.status = "RESOLVED"
    await db.commit()

    return InvestigationTriggerResponse(
        status="RESOLVED",
        anomaly_id=anomaly.id,
        message=f"Investigation completed with {final_state.get('confidence_score', 0.95) * 100:.1f}% confidence.",
    )


@router.get("/stream/{anomaly_id}")
async def stream_investigation_events(anomaly_id: int) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint streaming live agent thought traces and findings.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        async with AsyncSessionFactory() as session:
            stmt = select(AnomalyEvent).where(AnomalyEvent.id == anomaly_id)
            result = await session.execute(stmt)
            anomaly = result.scalar_one_or_none()

            if not anomaly:
                yield f"event: error\ndata: {json.dumps({'error': f'Anomaly #{anomaly_id} not found'})}\n\n"
                return

            # Yield Anomaly Info
            yield f"event: anomaly_info\ndata: {json.dumps({'id': anomaly.id, 'metric': anomaly.metric_name, 'region': anomaly.region, 'product': anomaly.product_name, 'severity': anomaly.severity, 'actual': anomaly.actual_value, 'expected': anomaly.expected_value, 'dataset_source': getattr(anomaly, 'dataset_source', 'FINTECH_90D')})}\n\n"
            await asyncio.sleep(0.1)

            # Build initial state
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
                "trigger_source": "SSE_STREAM",
                "dataset_source": getattr(anomaly, "dataset_source", "FINTECH_90D"),
                "active_hypothesis": f"Investigating {anomaly.metric_name} in {anomaly.region}.",
                "iteration_count": 0,
                "sql_history": [],
                "ticket_citations": [],
                "reasoning_trace": [],
            }

            graph_builder = InvestigationGraphBuilder()
            workflow = graph_builder.build_graph()

            # Stream steps through workflow.astream
            async for chunk in workflow.astream(initial_state):
                for node_name, node_state in chunk.items():
                    # Stream thoughts if any
                    for thought in node_state.get("reasoning_trace", []):
                        yield f"event: agent_thought\ndata: {json.dumps(thought)}\n\n"
                        await asyncio.sleep(0.05)

                    # Stream SQL evidence
                    for sql in node_state.get("sql_history", []):
                        yield f"event: sql_evidence\ndata: {json.dumps(sql)}\n\n"
                        await asyncio.sleep(0.05)

                    # Stream Ticket citations
                    for ticket in node_state.get("ticket_citations", []):
                        yield f"event: ticket_evidence\ndata: {json.dumps(ticket)}\n\n"
                        await asyncio.sleep(0.05)

                    # Stream final RCA report
                    if node_name == "synthesis_agent":
                        rca_payload = {
                            "root_cause_summary": node_state.get("root_cause_summary"),
                            "confidence_score": node_state.get("confidence_score"),
                            "mitigation_steps": node_state.get("mitigation_steps"),
                        }
                        yield f"event: rca_report\ndata: {json.dumps(rca_payload)}\n\n"

            yield f"event: complete\ndata: {json.dumps({'status': 'DONE', 'anomaly_id': anomaly_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
