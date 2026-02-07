"""
LangGraph Workflow Definition
Builds the compiled state machine:
  ENTRY -> query_router -> (specialist agent) -> END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from backend.agents.state import AgentState
from backend.agents.router import query_router
from backend.agents.tutor_agent import tutor_agent
from backend.agents.doubts_agent import doubts_agent
from backend.agents.personalised_agent import personalised_agent
from backend.agents.quiz_helper_agent import quiz_helper_agent
from backend.agents.feedback_agent import feedback_agent
from backend.config import config

logger = logging.getLogger(__name__)


def _route_next(state: AgentState) -> str:
    """Conditional edge: read ``state["next"]`` set by the router."""
    return state.get("next", "tutor_agent")


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph agent workflow."""
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("query_router", query_router)
    graph.add_node("tutor_agent", tutor_agent)
    graph.add_node("doubts_agent", doubts_agent)
    graph.add_node("personalised_agent", personalised_agent)
    graph.add_node("quiz_helper_agent", quiz_helper_agent)
    graph.add_node("feedback_agent", feedback_agent)

    # Entry
    graph.set_entry_point("query_router")

    # Conditional edges from router to specialist
    graph.add_conditional_edges(
        "query_router",
        _route_next,
        {
            "tutor_agent": "tutor_agent",
            "doubts_agent": "doubts_agent",
            "personalised_agent": "personalised_agent",
            "quiz_helper_agent": "quiz_helper_agent",
            "feedback_agent": "feedback_agent",
        },
    )

    # Each specialist goes straight to END
    for agent_node in [
        "tutor_agent",
        "doubts_agent",
        "personalised_agent",
        "quiz_helper_agent",
        "feedback_agent",
    ]:
        graph.add_edge(agent_node, END)

    return graph.compile()


# Singleton compiled graph
_compiled_graph = None


def get_compiled_graph():
    """Return (or build) the singleton compiled LangGraph."""
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("Building LangGraph agent workflow...")
        _compiled_graph = build_graph()
        logger.info("LangGraph agent workflow compiled successfully")
    return _compiled_graph
