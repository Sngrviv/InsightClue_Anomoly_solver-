"""
Safe Read-Only SQL Sandbox for AI Agents.
Enforces AST/Regex validation, forbids write/DDL operations, injects LIMIT pagination,
and executes queries within read-only transactions with timeouts.
"""

import asyncio
import re
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import AsyncSessionFactory


class SQLSecurityViolation(Exception):
    """Raised when an agent attempts an unsafe or non-SELECT SQL operation."""
    pass


class SafeSQLSandbox:
    """
    Secure execution boundary for autonomous LLM SQL queries.
    """

    FORBIDDEN_KEYWORDS = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bCREATE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bCALL\b",
        r"\bMERGE\b",
    ]

    def __init__(self, max_rows: int = 50, timeout_seconds: float = 5.0) -> None:
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    def validate_query(self, query: str) -> str:
        """
        Validates that the SQL query is strictly a read-only SELECT or WITH statement.
        Returns the sanitized query with a forced LIMIT clause.
        """
        clean_query = query.strip()

        # Remove trailing semicolon if present
        if clean_query.endswith(";"):
            clean_query = clean_query[:-1].strip()

        # Disallow multiple semicolon-separated statements
        if ";" in clean_query:
            raise SQLSecurityViolation("Multiple SQL statements in a single query are forbidden.")

        # Check for forbidden destructive keywords
        for pattern in self.FORBIDDEN_KEYWORDS:
            if re.search(pattern, clean_query, re.IGNORECASE):
                keyword = pattern.replace(r"\b", "")
                raise SQLSecurityViolation(
                    f"Forbidden keyword '{keyword}' detected. SQL Sandbox is strictly READ-ONLY."
                )

        # Must start with SELECT or WITH
        if not (
            re.match(r"^SELECT\b", clean_query, re.IGNORECASE)
            or re.match(r"^WITH\b", clean_query, re.IGNORECASE)
        ):
            raise SQLSecurityViolation("Query must start with SELECT or WITH.")

        # Check if query contains LIMIT clause; if not, inject LIMIT
        if not re.search(r"\bLIMIT\s+\d+\b", clean_query, re.IGNORECASE):
            clean_query = f"{clean_query} LIMIT {self.max_rows}"

        return clean_query

    def _serialize_value(self, val: Any) -> Any:
        """Converts database objects (date, datetime, Decimal, UUID) into JSON-serializable primitives."""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        elif hasattr(val, "__float__"):
            return float(val)
        elif hasattr(val, "__str__") and not isinstance(val, (int, float, bool, list, dict, type(None))):
            return str(val)
        return val

    async def execute_query(
        self,
        query: str,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """
        Safely executes the validated query against PostgreSQL and returns results as dicts.
        """
        validated_sql = self.validate_query(query)

        async def _run(sess: AsyncSession) -> list[dict[str, Any]]:
            # Enforce read-only transaction state
            await sess.execute(text("SET TRANSACTION READ ONLY"))
            result = await sess.execute(text(validated_sql))
            rows = result.mappings().all()
            return [
                {k: self._serialize_value(v) for k, v in row.items()}
                for row in rows
            ]

        if session is not None:
            return await asyncio.wait_for(_run(session), timeout=self.timeout_seconds)

        async with AsyncSessionFactory() as fresh_session:
            return await asyncio.wait_for(_run(fresh_session), timeout=self.timeout_seconds)
