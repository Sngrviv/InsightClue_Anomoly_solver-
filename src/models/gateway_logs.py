from datetime import date
from sqlalchemy import Date, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class PaymentGatewayLog(Base):
    """
    Tracks bank partner routing, 3DS authentication gateways, and API health metrics.
    Provides structured technical root-cause evidence for transaction failures.
    """

    __tablename__ = "payment_gateway_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    partner_bank: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gateway_channel: Mapped[str] = mapped_column(String(50), nullable=False)  # 3DS_OTP, DIRECT_API, IMPS_SWITCH

    # Traffic & Health Metrics
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_504_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    server_error_500_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_response_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    gateway_status: Mapped[str] = mapped_column(String(30), default="OPERATIONAL", nullable=False)  # OPERATIONAL, DEGRADED, OUTAGE

    __table_args__ = (
        Index("idx_gw_date_bank_product", "log_date", "partner_bank", "product_name"),
        Index("idx_gw_status", "gateway_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentGatewayLog(date={self.log_date}, bank='{self.partner_bank}', "
            f"channel='{self.gateway_channel}', status='{self.gateway_status}', "
            f"failures={self.failed_requests}, timeouts={self.timeout_504_count})>"
        )
