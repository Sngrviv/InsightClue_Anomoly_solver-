# 001 - Deepen TicketVectorStore Interface & Encapsulation

**Label**: `wayfinder:grilling`
**Status**: `closed`
**Assignee**: `Antigravity`
**Blocked by**: None

## Question

How should we collapse the shallow separation between `EmbeddingService` and `TicketVectorStore` into a single deep `TicketVectorStore` module? 

Specifically:
1. What should the exact narrow interface be for storing, searching, and filtering dispute tickets?
2. How should embedding generation, batch caching, pgvector `<=>` cosine distance querying, and ORM hydration be hidden entirely behind the seam?
3. What black-box test suite will act as the single test surface for all vector operations?

## Resolution

1. **Unified Deep Seam Interface**:
   - `TicketVectorStore` absorbs the embedding engine and exposes a minimal, high-leverage interface:
     - `async search(query: str, limit: int = 5, min_similarity: float = 0.5, **filters) -> list[TicketMatch]`
     - `async index_tickets(tickets: list[DisputeSupportTicket] | list[dict], batch_size: int = 128) -> int`
   - Direct calls from external adapters/scripts to raw embedding functions are replaced by `TicketVectorStore.index_tickets()`.
2. **Internal Encapsulation**:
   - Embedding generation (Gemini / local FastEmbed ONNX fallback), dimension validation (768-dim), padding/normalization, and chunked batch insertion are completely private to `TicketVectorStore`.
   - In-memory LRU caching is applied to query embeddings so repeated semantic searches within agent investigation loops execute instantly without redundant compute.
3. **Black-box Test Surface**:
   - `tests/test_ticket_vector_store.py` tests only the public seam: indexing batches, semantic cosine filtering, metadata constraints, and offline fallback.
