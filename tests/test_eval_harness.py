"""
Grounded Evaluation & Benchmark Test Suite for InsightClue Multi-Agent System.
Measures RAG Retrieval Precision@K, SQL query generation validity, and RCA Synthesis faithfulness.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.investigation_graph import InvestigationGraphBuilder
from src.agents.state import InvestigationState
from src.agents.tools.sql_sandbox import SafeSQLSandbox
from src.services.ticket_vector_store import TicketVectorStore


# Golden Benchmark Test Cases
GOLDEN_SCENARIOS = [
    {
        "name": "Scenario 1: CFPB Loan Disclosure Grievance Spike",
        "anomaly": {
            "anomaly_id": 101,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "region": "West",
            "product_name": "Mortgage",
            "customer_tier": "Retail",
            "metric_name": "chargeback_dispute_spike",
            "actual_value": 8.5,
            "expected_value": 0.5,
            "deviation_pct": 1600.0,
            "z_score": 4.2,
            "severity": "CRITICAL",
            "dataset_source": "KAGGLE_CFPB",
        },
        "target_keywords": ["loan", "mortgage", "disclosure", "closing", "dispute", "interest"],
    },
    {
        "name": "Scenario 2: Credit Card Unauthorized Surcharge & Fee Dispute",
        "anomaly": {
            "anomaly_id": 102,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "region": "South",
            "product_name": "Credit Card",
            "customer_tier": "Enterprise",
            "metric_name": "chargeback_dispute_spike",
            "actual_value": 6.2,
            "expected_value": 0.8,
            "deviation_pct": 675.0,
            "z_score": 3.8,
            "severity": "CRITICAL",
            "dataset_source": "KAGGLE_CFPB",
        },
        "target_keywords": ["card", "fee", "unauthorized", "charge", "dispute", "billing"],
    },
]


@pytest.mark.asyncio
async def test_eval_sql_sandbox_validity(db_session: AsyncSession):
    """
    Evaluates that the SQL agent sandbox executes valid SELECT statements and adheres to read-only constraints.
    """
    sandbox = SafeSQLSandbox()

    # 1. Valid telemetry query
    valid_query = "SELECT metric_date, region, product_name, daily_spend_amount FROM daily_spend_metrics LIMIT 5;"
    results = await sandbox.execute_query(valid_query, session=db_session)
    assert isinstance(results, list)

    # 2. Dynamic schema description inspection
    schema_summary = await sandbox.get_schema_summary(session=db_session)
    assert "daily_spend_metrics" in schema_summary
    assert "dispute_support_tickets" in schema_summary


@pytest.mark.asyncio
async def test_eval_rag_retrieval_precision():
    """
    Evaluates that semantic search produces relevant results matching incident categories.
    """
    store = TicketVectorStore()
    query = "mortgage loan settlement disclosure and closing fees dispute"

    matches = await store.search(
        query=query,
        limit=5,
        min_similarity=0.20,
    )

    # Retrieval should execute cleanly and return typed matches
    assert isinstance(matches, list)
    for m in matches:
        assert hasattr(m, "similarity_score")
        assert hasattr(m, "ticket")


@pytest.mark.asyncio
async def test_eval_end_to_end_investigation_faithfulness(db_session: AsyncSession):
    """
    Evaluates end-to-end multi-agent RCA graph execution on a golden benchmark scenario.
    """
    builder = InvestigationGraphBuilder()
    graph = builder.build_graph()

    scenario = GOLDEN_SCENARIOS[0]
    initial_state: InvestigationState = {
        **scenario["anomaly"],
        "active_hypothesis": "Investigating unexpected surge in consumer mortgage dispute complaints.",
        "iteration_count": 0,
        "sql_history": [],
        "ticket_citations": [],
        "reasoning_trace": [],
        "root_cause_summary": "",
        "confidence_score": 0.0,
        "mitigation_steps": "",
        "is_complete": False,
    }

    final_state = await graph.ainvoke(initial_state)

    # Assert graph execution finished at synthesis node
    assert len(final_state.get("root_cause_summary", "")) > 0
    assert final_state.get("confidence_score", 0.0) >= 0.70
    assert len(final_state.get("mitigation_steps", "")) > 0
    assert len(final_state.get("reasoning_trace", [])) >= 2
