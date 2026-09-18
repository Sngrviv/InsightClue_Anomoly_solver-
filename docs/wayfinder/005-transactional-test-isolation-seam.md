# 005 - Transactional Test Isolation Seam

**Label**: `wayfinder:grilling`
**Status**: `open`
**Assignee**: `unassigned`
**Blocked by**: None

## Question

How should `tests/conftest.py` provide strict transactional isolation with nested savepoints and automatic rollback so that tests never mutate the live development database or corrupt chart metrics?

Specifically:
1. How should SQLAlchemy async nested savepoints (`session.begin_nested()`) prevent test fixture data from leaking into live table rows?
2. How do we ensure FastAPI test client requests (`httpx.AsyncClient`) use the isolated test session dependency override?
