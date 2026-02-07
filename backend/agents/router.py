"""
Query Router Agent
Classifies user intent via keyword matching and routes to the correct
specialist agent. Logs the classified query to Neo4j.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Tuple

from backend.agents.state import AgentState
from backend.agents import graph_ops

logger = logging.getLogger(__name__)

# ── Keyword rules (order matters: first match wins) ──────────────

_RULES: list[Tuple[str, str, str]] = [
    # (agent_name, route_reason_template, regex_pattern)
    (
        "feedback_agent",
        "Detected feedback or opinion",
        r"\b(feedback|suggestion|great app|love this|hate|improve|satisfied|disappointed|"
        r"awesome|terrible|issue with|complaint|compliment|this app|the platform|thank you|thanks)\b",
    ),
    (
        "quiz_helper_agent",
        "Detected quiz-related query",
        r"\b(quiz|score|weak topic|strong topic|study plan|review|performance|"
        r"test result|what should i study|my results|my grades|how did i do|exam|assessment)\b",
    ),
    (
        "doubts_agent",
        "Detected confusion or doubt",
        r"\b(confused|don'?t understand|doubt|unclear|what (does|is|are)|"
        r"can you clarify|explain again|stuck on|struggling with|help me understand|"
        r"i'?m lost|makes no sense|difference between)\b",
    ),
    (
        "personalised_agent",
        "Detected request for personalised explanation",
        r"\b(explain|break down|in simple terms|eli5|analogy|like i'?m|"
        r"relate to|connect to what i know|tailor|my level|beginner|"
        r"step by step|walk me through|teach me)\b",
    ),
]


def classify_query(text: str) -> Tuple[str, str]:
    """Return (agent_name, route_reason) for the given query text."""
    lower = text.lower()
    for agent, reason, pattern in _RULES:
        if re.search(pattern, lower):
            return agent, reason
    return "tutor_agent", "General tutoring query (default)"


# ── LangGraph node ───────────────────────────────────────────────

def query_router(state: AgentState) -> Dict:
    """Entry node: classify intent → set ``next`` + ``route_reason``."""
    text = state["input"]
    user_id = state.get("user_id", "")
    agent_name, route_reason = classify_query(text)

    # Determine query_type label for logging
    query_type_map = {
        "tutor_agent": "general_tutoring",
        "doubts_agent": "doubt_resolution",
        "personalised_agent": "personalised_explanation",
        "quiz_helper_agent": "quiz_help",
        "feedback_agent": "feedback",
    }
    query_type = query_type_map.get(agent_name, "general_tutoring")

    # Neo4j: log the classified query
    graph_ops.log_query(user_id, text, query_type)

    logger.info("Router: %s -> %s (%s)", text[:60], agent_name, route_reason)

    return {
        "next": agent_name,
        "agent": agent_name,
        "route_reason": route_reason,
    }
