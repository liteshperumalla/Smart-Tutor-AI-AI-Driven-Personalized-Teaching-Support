"""
Agent State Definition
TypedDict that flows through the LangGraph state machine.
Each agent reads from and writes to this shared state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────
    input: str
    user_id: str
    session_id: str
    model_id: Optional[str]

    # ── Student profile (quiz_results + Neo4j) ───────────────────
    student_name: Optional[str]
    student_level: Optional[str]          # beginner / intermediate / advanced
    top_topics: Optional[List[str]]       # from quiz folders
    weak_topics: Optional[List[str]]      # lowest-scoring folders
    struggled_concepts: Optional[List[str]]  # from Neo4j
    recently_studied: Optional[List[str]]    # from Neo4j

    # ── Agent routing ─────────────────────────────────────────────
    response: str
    agent: str
    next: Optional[str]
    route_reason: Optional[str]

    # ── Conversation context ──────────────────────────────────────
    previous_query: Optional[str]
    previous_response: Optional[str]
    previous_agent: Optional[str]

    # ── Feedback ──────────────────────────────────────────────────
    feedback_recorded: Optional[bool]
    sentiment: Optional[str]

    # ── RAG context ───────────────────────────────────────────────
    retrieved_sources: Optional[List[Dict[str, Any]]]
    context_str: Optional[str]

    # ── Metadata ──────────────────────────────────────────────────
    timestamp: str
    retry_count: Optional[int]
