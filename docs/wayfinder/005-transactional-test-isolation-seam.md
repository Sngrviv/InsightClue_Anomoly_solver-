# 005 - Transactional Test Isolation Seam

**Label**: `wayfinder:grilling`
**Status**: `closed`
**Assignee**: `Antigravity`
**Blocked by**: None

## Resolution & Implementation

1. **Transactional Savepoint Isolation (`db_session`)**:
   - `conftest.py` provides an isolated `db_connection` fixture wrapped in an outer transaction that unconditionally rolls back on teardown.
   - `db_session` binds to this connection with `join_transaction_mode="create_savepoint"`. Any internal `session.commit()` calls in business code or test fixtures only commit the nested savepoint, never mutating or persisting records to the live PostgreSQL tables.
2. **Self-Contained Deterministic Seed Fixture (`seeded_db_session`)**:
   - Tests no longer depend on pre-existing database rows or external CSV data.
   - Known baselines (30-day FinTech metrics, CFPB complaints, payment gateway logs, and pgvector embeddings) are seeded directly into the savepoint and vanished on fixture teardown.
3. **FastAPI Dependency Override Seam (`api_client`)**:
   - `api_client` automatically injects `get_db = lambda: seeded_db_session` into FastAPI's `dependency_overrides`.
   - SSE and REST endpoints execute with zero database pollution.
4. **Verification**:
   - Verified via `tests/test_transaction_isolation.py`.
   - All 23 test suites pass 100% green with sub-second rollback.
