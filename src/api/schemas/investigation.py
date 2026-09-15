"""
Pydantic Schemas for Multi-Agent Investigation Reports and Streaming Events.
"""

"Strictly for type checking "

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class InvestigationTriggerResponse(BaseModel):
    status: str
    anomaly_id: int
    message: str


class InvestigationReportDetailResponse(BaseModel):
    id: int
    anomaly_id: int
    generated_at: datetime
    root_cause_summary: str
    confidence_score: float
    mitigation_steps: str
    evidence_data: dict[str, Any]
    reasoning_trace: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class SSEStreamEvent(BaseModel):
    event: str
    data: dict[str, Any]
