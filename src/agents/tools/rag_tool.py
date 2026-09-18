"""
Semantic RAG Retrieval Tool for AI Agents.
Wraps TicketVectorStore to query customer dispute tickets via natural language.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.state import TicketCitation
from src.services.ticket_vector_store import TicketVectorStore


class DisputeTicketRAGTool:
    """
    RAG Tool for the Vector RAG Agent to find relevant customer complaints.
    """

    def __init__(self, vector_store: TicketVectorStore | None = None) -> None:
        self.vector_store = vector_store or TicketVectorStore()

    async def search_tickets(
        self,
        query: str,
        region: str | None = None,
        product_name: str | None = None,
        customer_tier: str | None = None,
        dataset_source: str | None = None,
        limit: int = 5,
        session: AsyncSession | None = None,
    ) -> list[TicketCitation]:
        """
        Executes semantic search and formats results into serializable TicketCitation dicts.
        """
        matches = await self.vector_store.search(
            query=query,
            region=region,
            product_name=product_name,
            customer_tier=customer_tier,
            dataset_source=dataset_source,
            limit=limit,
            session=session,
        )

        citations: list[TicketCitation] = []
        for match in matches:
            ticket = match.ticket
            citations.append(
                TicketCitation(
                    ticket_id=ticket.id,
                    customer_id=ticket.customer_id,
                    issue_category=ticket.issue_category,
                    complaint_text=f"{ticket.subject}: {ticket.message}",
                    similarity_score=round(float(match.similarity_score), 4),
                )
            )

        return citations
