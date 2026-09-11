"""
Pydantic Schemas for Anomaly Events and Financial Metrics Overview.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MetricsOverviewResponse(BaseModel):
    total_spend_90d: float = Field(..., description="Total aggregate spend across 90 days")
    total_transactions: int = Field(..., description="Total transactions tracked")
    avg_success_rate_pct: float = Field(..., description="Global average success rate percentage")
    total_anomalies_detected: int = Field(..., description="Total anomalies discovered")
    open_anomalies_count: int = Field(..., description="Currently unresolved anomalies")
    critical_anomalies_count: int = Field(..., description="Critical severity anomalies count")


class AnomalyReportSummary(BaseModel):
    id: int
    generated_at: datetime
    root_cause_summary: str
    confidence_score: float
    mitigation_steps: str

    model_config = ConfigDict(from_attributes=True)


class AnomalyResponse(BaseModel):
    id: int
    detected_at: datetime
    metric_name: str
    region: str
    product_name: str
    customer_tier: str | None = None
    actual_value: float
    expected_value: float
    deviation_pct: float
    z_score: float
    severity: str
    status: str
    investigation: AnomalyReportSummary | None = None

    model_config = ConfigDict(from_attributes=True)


class AnomalyListResponse(BaseModel):
    total: int
    items: list[AnomalyResponse]


class AnomalyScanResponse(BaseModel):
    status: str
    new_anomalies_flagged: int
    message: str
