"""
Test suite for LangGraph Multi-Agent Investigation Architecture.
Verifies SafeSQLSandbox, DisputeTicketRAGTool, and Multi-Agent Workflow State Transitions.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.agents.tools.rag_tool import DisputeTicketRAGTool
from src.agents.tools.sql_sandbox import SafeSQLSandbox, SQLSecurityViolation


@pytest.mark.asyncio
async def test_sql_sandbox_blocks_destructive_queries() -> None:
    sandbox = SafeSQLSandbox()

    # Disallow DROP
    with pytest.raises(SQLSecurityViolation, match="Forbidden keyword 'DROP' detected"):
        sandbox.validate_query("DROP TABLE daily_spend_metrics;")

    # Disallow DELETE
    with pytest.raises(SQLSecurityViolation, match="Forbidden keyword 'DELETE' detected"):
        sandbox.validate_query("DELETE FROM payment_gateway_logs WHERE id = 1;")

    # Disallow UPDATE
    with pytest.raises(SQLSecurityViolation, match="Forbidden keyword 'UPDATE' detected"):
        sandbox.validate_query("UPDATE dispute_support_tickets SET priority = 'LOW';")

    # Disallow multiple statements
    with pytest.raises(SQLSecurityViolation, match="Multiple SQL statements"):
        sandbox.validate_query("SELECT * FROM payment_gateway_logs; DROP TABLE users;")


@pytest.mark.asyncio
async def test_sql_sandbox_executes_safe_select(db_session: AsyncSession) -> None:
    sandbox = SafeSQLSandbox()
    query = "SELECT count(*) as total_logs FROM payment_gateway_logs"
    results = await sandbox.execute_query(query, session=db_session)
    assert len(results) == 1
    assert "total_logs" in results[0]
    assert results[0]["total_logs"] > 0


@pytest.mark.asyncio
async def test_rag_tool_returns_citations(db_session: AsyncSession) -> None:
    rag_tool = DisputeTicketRAGTool()
    citations = await rag_tool.search_tickets(
        query="Corporate Card OTP timeout in South region",
        region="South",
        product_name="Corporate Credit Card",
        limit=3,
        session=db_session,
    )
    assert isinstance(citations, list)
    assert len(citations) > 0
    first = citations[0]
    assert "ticket_id" in first
    assert "complaint_text" in first
    assert first["similarity_score"] > 0.0


@pytest.mark.asyncio
async def test_multi_agent_investigation_state_transition(db_session: AsyncSession) -> None:
    graph_builder = InvestigationGraphBuilder()
    workflow = graph_builder.build_graph()

    initial_state: InvestigationState = {
        "anomaly_id": 9999,
        "region": "South",
        "product_name": "Corporate Credit Card",
        "customer_tier": "Enterprise",
        "metric_name": "success_rate_plunge",
        "actual_value": 74.0,
        "expected_value": 98.5,
        "deviation_pct": -24.87,
        "z_score": -20.4,
        "severity": "CRITICAL",
        "trigger_source": "METRIC_SCAN",
        "iteration_count": 0,
        "sql_history": [],
        "ticket_citations": [],
        "reasoning_trace": [],
    }

    final_state = await workflow.ainvoke(initial_state)

    assert final_state["is_complete"] is True
    assert final_state["confidence_score"] >= 0.0
    assert len(final_state["reasoning_trace"]) >= 2
    assert "root_cause_summary" in final_state
    assert "mitigation_steps" in final_state
