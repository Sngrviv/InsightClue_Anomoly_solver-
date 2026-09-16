"""
Anomaly inspection and on-demand detection trigger routes.
"""

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.api.schemas.anomaly import (
    AnomalyListResponse,
    AnomalyResponse,
    AnomalyScanResponse,
)
from src.database.session import get_db
from src.models.investigations import AnomalyEvent
from src.services.anomaly_detector import AnomalyDetectionEngine

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=AnomalyListResponse)
async def list_anomalies(
    status: Literal["OPEN", "INVESTIGATING", "RESOLVED"] | None = Query(None, description="Filter by status"),
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = Query(None, description="Filter by severity"),
    region: str | None = Query(None, description="Filter by geographic region"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    """
    Lists flagged anomalies with filtering and eager-loaded investigation summaries.
    """
    stmt = (
        select(AnomalyEvent)
        .options(selectinload(AnomalyEvent.investigation))
        .order_by(AnomalyEvent.detected_at.desc(), AnomalyEvent.id.desc())
    )

    if status:
        stmt = stmt.where(AnomalyEvent.status == status)
    if severity:
        stmt = stmt.where(AnomalyEvent.severity == severity)
    if region:
        stmt = stmt.where(AnomalyEvent.region == region)

    # Count total matching
    count_stmt = select(func.count(AnomalyEvent.id))
    if status:
        count_stmt = count_stmt.where(AnomalyEvent.status == status)
    if severity:
        count_stmt = count_stmt.where(AnomalyEvent.severity == severity)
    if region:
        count_stmt = count_stmt.where(AnomalyEvent.region == region)

    total_count = await db.scalar(count_stmt) or 0

    # Paginate
    paged_stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(paged_stmt)
    anomalies = result.scalars().all()

    return AnomalyListResponse(
        total=total_count,
        items=[AnomalyResponse.model_validate(a) for a in anomalies],
    )


@router.get("/{anomaly_id}", response_model=AnomalyResponse)
async def get_anomaly(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
) -> AnomalyResponse:
    """
    Retrieves detailed metadata for a specific anomaly event.
    """
    stmt = (
        select(AnomalyEvent)
        .options(selectinload(AnomalyEvent.investigation))
        .where(AnomalyEvent.id == anomaly_id)
    )
    result = await db.execute(stmt)
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly #{anomaly_id} not found.",
        )

    return AnomalyResponse.model_validate(anomaly)


@router.post("/detect", response_model=AnomalyScanResponse)
async def trigger_anomaly_detection(
    db: AsyncSession = Depends(get_db),
) -> AnomalyScanResponse:
    """
    Triggers the Rolling Z-Score and Isolation Forest detection engine across all daily spend metrics.
    """
    engine = AnomalyDetectionEngine()
    persisted = await engine.scan_and_persist(session=db)

    return AnomalyScanResponse(
        status="COMPLETED",
        new_anomalies_flagged=len(persisted),
        message=f"Successfully scanned metrics and persisted {len(persisted)} anomaly events.",
    )
