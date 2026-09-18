from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base


class AnomalyEvent(Base):
    """
    Stores detected metric anomalies flagged by statistical/ML anomaly detection models.
    Acts as the trigger point for Multi-Agent AI investigations.
    """

    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_source: Mapped[str] = mapped_column(String(50), default="FINTECH_90D", nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)  # success_rate_plunge, spend_volume_drop, dispute_rate_spike
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    customer_tier: Mapped[str] = mapped_column(String(50), nullable=True)

    # Anomaly Quantifications
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_pct: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)  # OPEN, INVESTIGATING, RESOLVED

    # Relationship to Investigation Report
    investigation: Mapped["InvestigationReport"] = relationship(
        "InvestigationReport",
        back_populates="anomaly",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_anomaly_status_severity", "status", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnomalyEvent(id={self.id}, metric='{self.metric_name}', "
            f"region='{self.region}', product='{self.product_name}', "
            f"actual={self.actual_value:.2f}, expected={self.expected_value:.2f}, "
            f"severity='{self.severity}', status='{self.status}')>"
        )


class InvestigationReport(Base):
    """
    Stores the synthesized Root Cause Analysis (RCA) report created by the Multi-Agent team.
    Includes structured findings, SQL query proofs, RAG ticket citations, and mitigation plans.
    """

    __tablename__ = "investigation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("anomaly_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    root_cause_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0

    # Structured Agent Artifacts
    evidence_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reasoning_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    mitigation_steps: Mapped[str] = mapped_column(Text, nullable=False)

    # Back-reference to Anomaly
    anomaly: Mapped["AnomalyEvent"] = relationship("AnomalyEvent", back_populates="investigation")

    def __repr__(self) -> str:
        return (
            f"<InvestigationReport(id={self.id}, anomaly_id={self.anomaly_id}, "
            f"confidence={self.confidence_score:.2f})>"
        )
