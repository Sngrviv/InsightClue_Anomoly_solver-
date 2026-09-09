"""
Tests for TicketVectorStore deep semantic search and metadata filtering seam.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.ticket_vector_store import TicketVectorStore


@pytest.mark.asyncio
async def test_ticket_vector_store_semantic_search(db_session: AsyncSession):
    store = TicketVectorStore()
    query = "Corporate card 3DS OTP timeout on supplier invoice"

    matches = await store.search(
        query=query,
        limit=3,
        min_similarity=0.50,
        session=db_session,
    )

    assert len(matches) > 0
    top_match = matches[0]
    assert top_match.similarity_score >= 0.70
    assert top_match.ticket.product_name == "Corporate Credit Card"
    assert top_match.ticket.region == "South"
    assert "OTP" in top_match.ticket.subject or "OTP" in top_match.ticket.message


@pytest.mark.asyncio
async def test_ticket_vector_store_regional_filter(db_session: AsyncSession):
    store = TicketVectorStore()
    query = "Dispute regarding transaction clearance"

    matches = await store.search(
        query=query,
        limit=5,
        region="West",
        min_similarity=0.40,
        session=db_session,
    )

    for m in matches:
        assert m.ticket.region == "West"


@pytest.mark.asyncio
async def test_ticket_vector_store_empty_query():
    store = TicketVectorStore()
    matches = await store.search(query="")
    assert matches == []
