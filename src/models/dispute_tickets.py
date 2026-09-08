from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base

# Vector embedding dimension: 768 (Matches Gemini text-embedding-004 standard)
EMBEDDING_DIMENSION = 768


class DisputeSupportTicket(Base):
    """
    Customer dispute, chargeback escalations, and payment issue tickets.
    Includes a 768-dimensional pgvector column for semantic RAG search and AI clustering.
    """

    __tablename__ = "dispute_support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    customer_tier: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Retail, Priority, Enterprise
    customer_id: Mapped[str] = mapped_column(String(50), nullable=False)

    issue_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 3DS_OTP_FAILURE, DOUBLE_DEBIT, FX_RATE_DISPUTE, MERCHANT_CHARGEBACK, ACCOUNT_HOLD

    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False)  # LOW, NORMAL, HIGH, CRITICAL
    dispute_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # -1.0 (angry) to +1.0 (happy)
    
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # pgvector Embedding Column for Semantic RAG Search
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)

    __table_args__ = (
        Index("idx_ticket_date_region", "ticket_created_at", "region"),
        Index("idx_ticket_category_tier", "issue_category", "customer_tier"),
    )

    def __repr__(self) -> str:
        return (
            f"<DisputeSupportTicket(id={self.id}, date={self.ticket_created_at.date()}, "
            f"tier='{self.customer_tier}', product='{self.product_name}', "
            f"category='{self.issue_category}', priority='{self.priority}')>"
        )
