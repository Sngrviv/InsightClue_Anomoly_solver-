from datetime import date
from sqlalchemy import Date, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class DailySpendMetric(Base):
    """
    Aggregated daily financial transaction and spend metrics across products, regions, and customer tiers.
    Tracks core KPIs: spend amount, volume, success rate, latency, chargebacks, and fraud scores.
    """

    __tablename__ = "daily_spend_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_source: Mapped[str] = mapped_column(String(50), default="FINTECH_90D", nullable=False, index=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    customer_tier: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    merchant_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Core Transaction & Spend Volume Metrics
    daily_spend_amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_ticket_size: Mapped[float] = mapped_column(Float, nullable=False)

    # Performance & Risk Metrics
    success_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 100.0
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    chargeback_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 100.0
    avg_fraud_risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 100.0

    __table_args__ = (
        Index("idx_spend_date_region_product", "metric_date", "region", "product_name"),
        Index("idx_spend_tier_category", "customer_tier", "merchant_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<DailySpendMetric(date={self.metric_date}, region='{self.region}', "
            f"product='{self.product_name}', tier='{self.customer_tier}', "
            f"spend={self.daily_spend_amount:,.2f}, success_rate={self.success_rate_pct:.1f}%)>"
        )
