"""
Deep Vector Store & Semantic Search Module for DisputeSupportTicket.
Encapsulates embedding generation, pgvector cosine distance operations,
metadata filtering, and ORM hydration behind a clean, high-leverage interface.
"""

from dataclasses import dataclass
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import AsyncSessionFactory
from src.models.dispute_tickets import DisputeSupportTicket
from src.services.embedding_service import generate_embedding


@dataclass(frozen=True)
class TicketMatch:
    """Represents a semantically matched support ticket with its cosine similarity score."""

    ticket: DisputeSupportTicket
    similarity_score: float


class TicketVectorStore:
    """
    High-level repository seam for semantic RAG search over customer dispute tickets.
    Hides embedding generation, pgvector cosine distance, and metadata filtering.
    """

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.50,
        region: str | None = None,
        product_name: str | None = None,
        customer_tier: str | None = None,
        issue_category: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[TicketMatch]:
        """
        Executes semantic vector similarity search against dispute support tickets.
        """
        if not query.strip():
            return []

        # 1. Generate query embedding vector using matched model space
        query_embedding = generate_embedding(query.strip(), prefer_gemini=False)

        # 2. Build type-safe SQLAlchemy ORM select statement
        sim_expr = (1 - DisputeSupportTicket.embedding.cosine_distance(query_embedding)).label("similarity_score")
        
        stmt = (
            select(DisputeSupportTicket, sim_expr)
            .where(DisputeSupportTicket.embedding.is_not(None))
            .where(sim_expr >= min_similarity)
        )

        if region:
            stmt = stmt.where(DisputeSupportTicket.region == region)

        if product_name:
            stmt = stmt.where(DisputeSupportTicket.product_name == product_name)

        if customer_tier:
            stmt = stmt.where(DisputeSupportTicket.customer_tier == customer_tier)

        if issue_category:
            stmt = stmt.where(DisputeSupportTicket.issue_category == issue_category)

        if start_date:
            stmt = stmt.where(DisputeSupportTicket.ticket_created_at >= start_date)

        if end_date:
            stmt = stmt.where(DisputeSupportTicket.ticket_created_at <= end_date)

        stmt = stmt.order_by(DisputeSupportTicket.embedding.cosine_distance(query_embedding)).limit(limit)

        # 3. Execute query
        if session is not None:
            return await self._execute_and_map(session, stmt)

        async with AsyncSessionFactory() as fresh_session:
            return await self._execute_and_map(fresh_session, stmt)

    async def _execute_and_map(
        self,
        session: AsyncSession,
        stmt,
    ) -> list[TicketMatch]:
        """Executes query and formats results into TicketMatch dataclass."""
        result = await session.execute(stmt)
        rows = result.all()

        return [
            TicketMatch(ticket=ticket, similarity_score=float(score))
            for ticket, score in rows
        ]
