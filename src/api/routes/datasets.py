"""
Dataset Ingestion and Partition Management Routes.
Exposes endpoints for file schema inference, chunked dataset ingestion, and dataset listing.
"""

import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.services.dynamic_ingestion import (
    DatasetMapping,
    DynamicIngestionEngine,
    IngestionSummary,
    InferredSchema,
)
from src.services.telemetry_store import TelemetryMetricStore

router = APIRouter(prefix="/datasets", tags=["Dataset Management"])
_telemetry_store = TelemetryMetricStore()


@router.get("", response_model=list[str])
@router.get("/list", response_model=list[str])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """
    Returns all active dataset partitions currently indexed in the system.
    """
    return await _telemetry_store.list_datasets(session=db)


@router.post("/upload", response_model=InferredSchema)
async def upload_and_infer_schema(
    file: UploadFile = File(...),
) -> InferredSchema:
    """
    Parses uploaded dataset file (CSV, JSON, Parquet) and returns inferred column roles.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        schema = DynamicIngestionEngine.infer_schema(content=content, filename=file.filename)
        return schema
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to infer schema from file: {str(exc)}",
        )


@router.post("/ingest", response_model=IngestionSummary)
@router.post("/confirm-ingestion", response_model=IngestionSummary)
async def ingest_dataset(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> IngestionSummary:
    """
    Ingests full dataset using confirmed column mapping.
    Populates telemetry metrics and generates FastEmbed embeddings if a text narrative is provided.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        mapping_data = json.loads(mapping) if isinstance(mapping, str) else mapping
        dataset_mapping = DatasetMapping(**mapping_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mapping configuration JSON: {str(exc)}",
        )

    try:
        summary = await DynamicIngestionEngine.ingest_dataset(
            db=db,
            content=content,
            filename=file.filename,
            mapping=dataset_mapping,
        )
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}",
        )
