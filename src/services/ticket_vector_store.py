"""
Deep Vector Store & Semantic Search Module for DisputeSupportTicket.
Encapsulates embedding generation, in-memory query caching, pgvector cosine distance operations,
batch ticket indexing, metadata filtering, and ORM hydration behind a clean, high-leverage interface.
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
import logging
import os
from typing import Any, Sequence
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.settings import get_settings
from src.database.session import AsyncSessionFactory
from src.models.dispute_tickets import EMBEDDING_DIMENSION, DisputeSupportTicket

logger = logging.getLogger(__name__)
settings = get_settings()

# Internal lazy-loaded clients
_gemini_client = None
_local_embedding_model = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                from google import genai
                _gemini_client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.warning(f"[VectorStore] Failed to initialize Gemini Client: {e}. Falling back to FastEmbed.")
                _gemini_client = False
        else:
            _gemini_client = False
    return _gemini_client


def _get_local_model():
    global _local_embedding_model
    if _local_embedding_model is None:
        from fastembed import TextEmbedding
        _local_embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _local_embedding_model


def _pad_or_truncate_vector(vec: list[float] | np.ndarray, target_dim: int = EMBEDDING_DIMENSION) -> list[float]:
    """Ensures embedding vector precisely matches the target dimension (768) and is L2-normalized."""
    arr = np.array(vec, dtype=np.float32)
    current_dim = len(arr)
    if current_dim == target_dim:
        norm = np.linalg.norm(arr)
        return (arr / norm).tolist() if norm > 0 else arr.tolist()
    elif current_dim < target_dim:
        padded = np.pad(arr, (0, target_dim - current_dim), mode="constant")
        norm = np.linalg.norm(padded)
        return (padded / norm).tolist() if norm > 0 else padded.tolist()
    else:
        truncated = arr[:target_dim]
        norm = np.linalg.norm(truncated)
        return (truncated / norm).tolist() if norm > 0 else truncated.tolist()


def _compute_embeddings_batch(texts: Sequence[str], prefer_gemini: bool = False) -> list[list[float]]:
    """Private batch embedding generator utilizing Gemini or FastEmbed ONNX."""
    if not texts:
        return []

    if prefer_gemini and len(texts) <= 5:
        client = _get_gemini_client()
        if client:
            try:
                embeddings = []
                for t in texts:
                    resp = client.models.embed_content(
                        model="gemini-embedding-2",
                        contents=t,
                        config={"output_dimensionality": EMBEDDING_DIMENSION},
                    )
                    if resp.embeddings and resp.embeddings[0].values is not None:
                        embeddings.append(_pad_or_truncate_vector(resp.embeddings[0].values, EMBEDDING_DIMENSION))
                    else:
                        raise ValueError("Gemini API returned empty embedding response.")
                return embeddings
            except Exception as e:
                logger.warning(f"[VectorStore] Gemini Embedding API error ({e}). Using local FastEmbed.")

    local_model = _get_local_model()
    raw_embeddings = list(local_model.embed(texts))
    return [_pad_or_truncate_vector(emb, EMBEDDING_DIMENSION) for emb in raw_embeddings]


@lru_cache(maxsize=1024)
def _cached_query_embedding_sync(query: str) -> tuple[float, ...]:
    """In-memory LRU cache for single query embeddings to prevent redundant compute in agent loops."""
    emb = _compute_embeddings_batch([query], prefer_gemini=False)[0]
    return tuple(emb)


@dataclass(frozen=True)
class TicketMatch:
    """Represents a semantically matched support ticket with its cosine similarity score."""

    ticket: DisputeSupportTicket
    similarity_score: float


class TicketVectorStore:
    """
    Deep repository seam for semantic search and batch indexing over customer dispute tickets.
    Hides embedding generation, dimension normalization, pgvector cosine distance, and caching.
    """

    async def get_query_embedding(self, query: str) -> list[float]:
        """Returns the 768-dim normalized embedding for a query string, utilizing in-memory LRU caching."""
        clean_query = query.strip()
        if not clean_query:
            return [0.0] * EMBEDDING_DIMENSION
        tuple_emb = await asyncio.to_thread(_cached_query_embedding_sync, clean_query)
        return list(tuple_emb)

    async def index_tickets(
        self,
        tickets: list[DisputeSupportTicket] | list[dict[str, Any]],
        batch_size: int = 128,
        dataset_source: str = "SYNTHETIC_SIMULATION",
        session: AsyncSession | None = None,
    ) -> int:
        """
        Batch-indexes dispute tickets: generates 768-dim embeddings and saves records to PostgreSQL + pgvector.
        Accepts either ORM instances or raw dictionaries.
        """
        if not tickets:
            return 0

        inserted_count = 0
        total = len(tickets)

        if session is not None:
            return await self._process_and_insert_batch(session, tickets, batch_size, dataset_source)

        async with AsyncSessionFactory() as fresh_session:
            async with fresh_session.begin():
                inserted_count = await self._process_and_insert_batch(
                    fresh_session, tickets, batch_size, dataset_source
                )
            return inserted_count

    async def _process_and_insert_batch(
        self,
        session: AsyncSession,
        tickets: list[DisputeSupportTicket] | list[dict[str, Any]],
        batch_size: int,
        dataset_source: str,
    ) -> int:
        inserted = 0
        total = len(tickets)
        total_batches = (total + batch_size - 1) // batch_size

        for batch_idx, i in enumerate(range(0, total, batch_size), start=1):
            chunk = tickets[i : i + batch_size]
            messages: list[str] = []
            ticket_entities: list[DisputeSupportTicket] = []

            for item in chunk:
                if isinstance(item, dict):
                    msg = str(item.get("message", item.get("subject", ""))).strip()
                else:
                    msg = str(item.message or item.subject or "").strip()
                # Truncate to first 1024 characters for FastEmbed ONNX token window efficiency
                messages.append(msg[:1024])

            print(f"   - [Batch {batch_idx}/{total_batches}] Generating 768-dim embeddings for {len(chunk)} tickets...")
            # Compute embeddings in worker thread to prevent event-loop block
            embeddings = await asyncio.to_thread(_compute_embeddings_batch, messages, False)

            for item, emb in zip(chunk, embeddings):
                if isinstance(item, dict):
                    entity = DisputeSupportTicket(
                        dataset_source=item.get("dataset_source", dataset_source),
                        ticket_created_at=item.get("ticket_created_at", datetime.now(timezone.utc)),
                        region=item.get("region", "West"),
                        product_name=item.get("product_name", "General"),
                        customer_tier=item.get("customer_tier", "Retail"),
                        customer_id=item.get("customer_id", "CUST-UNKNOWN"),
                        issue_category=item.get("issue_category", "General"),
                        priority=item.get("priority", "NORMAL"),
                        dispute_amount=float(item.get("dispute_amount", 0.0)),
                        sentiment_score=float(item.get("sentiment_score", 0.0)),
                        subject=item.get("subject", ""),
                        message=item.get("message", ""),
                        embedding=emb,
                    )
                else:
                    item.embedding = emb
                    entity = item

                session.add(entity)
                inserted += 1

            await session.flush()
            print(f"   - ✅ [Batch {batch_idx}/{total_batches}] Indexed {inserted:,}/{total:,} tickets into pgvector.")

        return inserted

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.50,
        region: str | None = None,
        product_name: str | None = None,
        customer_tier: str | None = None,
        issue_category: str | None = None,
        dataset_source: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[TicketMatch]:
        """
        Executes semantic vector similarity search against dispute support tickets.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Fetch cached query embedding
        query_embedding = await self.get_query_embedding(clean_query)

        # 2. Build SQLAlchemy ORM select statement
        sim_expr = (1 - DisputeSupportTicket.embedding.cosine_distance(query_embedding)).label("similarity_score")

        stmt = (
            select(DisputeSupportTicket, sim_expr)
            .where(DisputeSupportTicket.embedding.is_not(None))
            .where(sim_expr >= min_similarity)
        )

        if dataset_source:
            stmt = stmt.where(DisputeSupportTicket.dataset_source == dataset_source)

        if region:
            stmt = stmt.where(DisputeSupportTicket.region == region)

        if product_name:
            stmt = stmt.where(DisputeSupportTicket.product_name.ilike(f"%{product_name.strip()}%"))

        if customer_tier:
            stmt = stmt.where(DisputeSupportTicket.customer_tier.ilike(f"%{customer_tier.strip()}%"))

        if issue_category:
            stmt = stmt.where(DisputeSupportTicket.issue_category.ilike(f"%{issue_category.strip()}%"))

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
