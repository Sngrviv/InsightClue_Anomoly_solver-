"""
Anomaly inspection and on-demand detection trigger routes.
Supports partitioned dataset querying for FinTech Telemetry vs Kaggle CFPB Grievances.
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
    dataset_source: str = Query("FINTECH_90D", description="Dataset partition to query (FINTECH_90D or KAGGLE_CFPB)"),
    status: Literal["OPEN", "INVESTIGATING", "RESOLVED"] | None = Query(None, description="Filter by status"),
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = Query(None, description="Filter by severity"),
    region: str | None = Query(None, description="Filter by geographic region"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    """
    Lists flagged anomalies for the selected dataset with filtering and eager-loaded investigation summaries.
    """
    stmt = (
        select(AnomalyEvent)
        .options(selectinload(AnomalyEvent.investigation))
        .where(AnomalyEvent.dataset_source == dataset_source)
        .order_by(AnomalyEvent.detected_at.desc(), AnomalyEvent.id.desc())
    )

    if status:
        stmt = stmt.where(AnomalyEvent.status == status)
    if severity:
        stmt = stmt.where(AnomalyEvent.severity == severity)
    if region:
        stmt = stmt.where(AnomalyEvent.region == region)

    # Count total matching
    count_stmt = select(func.count(AnomalyEvent.id)).where(AnomalyEvent.dataset_source == dataset_source)
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
    dataset_source: str = Query("FINTECH_90D", description="Dataset partition to scan (FINTECH_90D or KAGGLE_CFPB)"),
    db: AsyncSession = Depends(get_db),
) -> AnomalyScanResponse:
    """
    Triggers the Rolling Z-Score and Isolation Forest detection engine across all metrics for the requested dataset.
    """
    engine = AnomalyDetectionEngine()
    persisted = await engine.scan_and_persist(session=db, dataset_source=dataset_source)

    return AnomalyScanResponse(
        status="COMPLETED",
        new_anomalies_flagged=len(persisted),
        message=f"Successfully scanned {dataset_source} telemetry and persisted {len(persisted)} anomaly events.",
    )


@router.post("/ingest-cfpb", response_model=AnomalyScanResponse)
async def trigger_cfpb_ingestion(
    limit: int = Query(250, ge=10, le=2000, description="Number of complaint narratives to ingest"),
    db: AsyncSession = Depends(get_db),
) -> AnomalyScanResponse:
    """
    Ingests, normalizes, and embeds real-world Kaggle CFPB consumer grievances into PostgreSQL & pgvector,
    then automatically runs anomaly detection on CFPB metrics.
    """
    from pathlib import Path
    from src.adapters.dataset_adapter import UniversalDatasetAdapter, CFPB_MAPPING

    # Prefer sqlite if present, else csv
    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "Data"
    sqlite_path = data_dir / "database.sqlite"
    csv_path = data_dir / "consumer_complaints.csv"
    source = sqlite_path if sqlite_path.exists() else csv_path

    if not source.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kaggle CFPB dataset file (database.sqlite or consumer_complaints.csv) not found in Data/ directory.",
        )

    adapter = UniversalDatasetAdapter()
    res = await adapter.ingest_dataset(
        source_path=source,
        mapping=CFPB_MAPPING,
        session=db,
        max_records=limit,
        dataset_source="KAGGLE_CFPB",
    )

    # Re-scan anomaly engine on CFPB partition
    engine = AnomalyDetectionEngine()
    persisted = await engine.scan_and_persist(session=db, dataset_source="KAGGLE_CFPB")

    return AnomalyScanResponse(
        status="COMPLETED",
        new_anomalies_flagged=len(persisted),
        message=f"Ingested & embedded {res.tickets_inserted} CFPB complaints into pgvector in {res.duration_seconds:.1f}s. Discovered {len(persisted)} grievance anomalies.",
    )
