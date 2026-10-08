"""
Safe Read-Only SQL Sandbox for AI Agents.
Delegates to the deep TelemetryMetricStore seam for query validation, schema introspection, and read-only execution.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.telemetry_store import TelemetryMetricStore, SQLSecurityViolation


class SafeSQLSandbox:
    """
    Secure execution boundary for autonomous LLM SQL queries.
    Provides dynamic schema introspection and read-only query execution via TelemetryMetricStore.
    """

    def __init__(self, max_rows: int = 50, timeout_seconds: float = 5.0, store: TelemetryMetricStore | None = None) -> None:
        self.store = store or TelemetryMetricStore(max_rows=max_rows, timeout_seconds=timeout_seconds)
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    async def get_schema_summary(self, session: AsyncSession | None = None) -> str:
        """Dynamically introspects PostgreSQL table schemas and returns a formatted description for LLM agents."""
        return await self.store.get_schema_summary(session=session)

    def validate_query(self, query: str) -> str:
        """Validates that the SQL query is strictly a read-only SELECT or WITH statement."""
        return self.store.validate_query(query)

    async def execute_query(
        self,
        query: str,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Safely executes the validated query against PostgreSQL and returns results as dicts."""
        return await self.store.execute_sandboxed_query(query=query, session=session)

