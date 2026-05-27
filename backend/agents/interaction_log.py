"""
Neo4j Agent Interaction Logger
Persists every agent interaction as an AgentInteraction node in the knowledge graph.
Uses the same fire-and-forget pattern as graph_ops.py.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.agents.graph_ops import _safe_write, _now_iso, _STUDENT_MERGE

logger = logging.getLogger(__name__)


def log_agent_interaction(
    username: str,
    session_id: str,
    query: str,
    response: str,
    agent: str,
    route_reason: Optional[str] = None,
    query_type: Optional[str] = None,
    sentiment: Optional[str] = None,
    feedback_category: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    model_id: Optional[str] = None,
) -> None:
    """Create an AgentInteraction node linked to the Student. Fire-and-forget."""
    _safe_write(
        _STUDENT_MERGE +
        "CREATE (ai:AgentInteraction {"
        "  session_id: $session_id,"
        "  query: $query,"
        "  response: $response,"
        "  agent: $agent,"
        "  route_reason: $route_reason,"
        "  query_type: $query_type,"
        "  sentiment: $sentiment,"
        "  feedback_category: $feedback_category,"
        "  response_time_ms: $response_time_ms,"
        "  model_id: $model_id,"
        "  timestamp: $ts"
        "}) "
        "CREATE (s)-[:HAD_AGENT_INTERACTION]->(ai)",
        {
            "username": username,
            "session_id": session_id,
            "query": query,
            "response": response,
            "agent": agent,
            "route_reason": route_reason,
            "query_type": query_type,
            "sentiment": sentiment,
            "feedback_category": feedback_category,
            "response_time_ms": response_time_ms,
            "model_id": model_id,
            "ts": _now_iso(),
        },
    )
