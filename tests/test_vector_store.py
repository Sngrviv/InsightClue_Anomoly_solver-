"""
Tests for TicketVectorStore deep semantic search, batch indexing, and embedding seam.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dispute_tickets import EMBEDDING_DIMENSION
from src.services.ticket_vector_store import TicketVectorStore


@pytest.mark.asyncio
async def test_ticket_vector_store_index_and_search(db_session: AsyncSession):
    store = TicketVectorStore()

    # 1. Prepare raw ticket records without pre-computed embeddings
    raw_tickets = [
        {
            "subject": "[UPI Instant Pay] 3DS OTP Gateway Failure",
            "message": "Customer experienced continuous 3DS OTP timeout errors while checking out on mobile app.",
            "region": "South",
            "product_name": "UPI Instant Pay",
            "customer_tier": "Priority",
            "customer_id": "CUST-TEST-001",
            "issue_category": "Authentication Timeout",
            "priority": "HIGH",
            "dispute_amount": 1250.0,
            "sentiment_score": -0.85,
            "ticket_created_at": datetime.now(timezone.utc),
            "dataset_source": "TEST_SEED",
        },
        {
            "subject": "[Corporate Credit Card] FX Fee Dispute",
            "message": "Disputing foreign exchange conversion surcharge on overseas business trip expense.",
            "region": "West",
            "product_name": "Corporate Credit Card",
            "customer_tier": "Enterprise",
            "customer_id": "CUST-TEST-002",
            "issue_category": "Fee Dispute",
            "priority": "NORMAL",
            "dispute_amount": 450.0,
            "sentiment_score": -0.3,
            "ticket_created_at": datetime.now(timezone.utc),
            "dataset_source": "TEST_SEED",
        },
    ]

    # 2. Test deep indexing seam
    inserted_count = await store.index_tickets(
        tickets=raw_tickets,
        batch_size=10,
        session=db_session,
    )
    assert inserted_count == 2

    # 3. Test semantic search against indexed tickets
    matches = await store.search(
        query="3DS mobile OTP timeout error during transaction",
        limit=2,
        min_similarity=0.40,
        session=db_session,
    )

    assert len(matches) > 0
    top_match = matches[0]
    assert top_match.ticket.product_name == "UPI Instant Pay"
    assert top_match.ticket.region == "South"
    assert len(top_match.ticket.embedding) == EMBEDDING_DIMENSION
    assert top_match.similarity_score >= 0.50


@pytest.mark.asyncio
async def test_ticket_vector_store_empty_query():
    store = TicketVectorStore()
    matches = await store.search(query="")
    assert matches == []


@pytest.mark.asyncio
async def test_ticket_vector_store_empty_index(db_session: AsyncSession):
    store = TicketVectorStore()
    count = await store.index_tickets([], session=db_session)
    assert count == 0


@pytest.mark.asyncio
async def test_ticket_vector_store_query_caching():
    store = TicketVectorStore()
    query = "Repeated network switch latency degradation"

    # Direct check of underlying cached vector retrieval
    emb1 = await store.get_query_embedding(query)
    emb2 = await store.get_query_embedding(query)

    assert len(emb1) == EMBEDDING_DIMENSION
    assert emb1 == emb2
