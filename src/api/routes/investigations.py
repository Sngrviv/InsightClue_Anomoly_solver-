"""
Multi-Agent RCA investigation execution and real-time SSE streaming routes.
Powered by the deep InvestigationService seam.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas.investigation import (
    InvestigationReportDetailResponse,
    InvestigationTriggerResponse,
)
from src.database.session import get_db
from src.models.investigations import AnomalyEvent, InvestigationReport
from src.services.investigation_service import InvestigationService

router = APIRouter(prefix="/investigations", tags=["Multi-Agent Investigations"])
_investigation_service = InvestigationService()


@router.get("/reports/{anomaly_id}", response_model=InvestigationReportDetailResponse)
async def get_investigation_report(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
) -> InvestigationReportDetailResponse:
    """Retrieves the complete synthesized RCA report with all SQL queries and ticket citations."""
    stmt = select(InvestigationReport).where(InvestigationReport.anomaly_id == anomaly_id)
    report = (await db.execute(stmt)).scalar_one_or_none()

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
    """Synchronously triggers the multi-agent investigation squad for an anomaly."""
    try:
        report = await _investigation_service.run_investigation(anomaly_id=anomaly_id, session=db)
        return InvestigationTriggerResponse(
            status="RESOLVED",
            anomaly_id=anomaly_id,
            message=f"Investigation completed with {report.confidence_score * 100:.1f}% confidence.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/stream/{anomaly_id}")
async def stream_investigation_events(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint streaming live agent thought traces and findings."""
    return StreamingResponse(
        _investigation_service.stream_investigation_events(anomaly_id=anomaly_id, session=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
