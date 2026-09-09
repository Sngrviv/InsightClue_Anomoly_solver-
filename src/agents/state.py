"""
Investigation State definition for LangGraph Multi-Agent Architecture.
Acts as the central blackboard state across Supervisor, SQL, RAG, and Synthesis nodes.
"""

from typing import Annotated, Any, Sequence, TypedDict
import operator


class SQLQueryResult(TypedDict):
    query: str
    row_count: int
    data: list[dict[str, Any]]
    error: str | None
    explanation: str


class TicketCitation(TypedDict):
    ticket_id: int
    customer_id: str
    issue_category: str
    complaint_text: str
    similarity_score: float


class AgentThought(TypedDict):
    agent: str
    thought: str
    timestamp: str


def append_list(a: list[Any], b: list[Any]) -> list[Any]:
    """Reducer that appends new items to an existing list."""
    return a + b


class InvestigationState(TypedDict, total=False):
    """
    Central blackboard state for InsightClue Multi-Agent Investigation.
    """

    # Anomaly Context
    anomaly_id: int
    detected_at: str
    region: str
    product_name: str
    customer_tier: str | None
    metric_name: str
    actual_value: float
    expected_value: float
    deviation_pct: float
    z_score: float
    severity: str
    trigger_source: str

    # Agent Investigation Tracks
    active_hypothesis: str
    next_agent: str
    iteration_count: int

    # Evidence Streams (using append reducers)
    sql_history: Annotated[list[SQLQueryResult], append_list]
    ticket_citations: Annotated[list[TicketCitation], append_list]
    reasoning_trace: Annotated[list[AgentThought], append_list]

    # Final RCA Synthesis
    root_cause_summary: str
    confidence_score: float
    mitigation_steps: str
    is_complete: bool
