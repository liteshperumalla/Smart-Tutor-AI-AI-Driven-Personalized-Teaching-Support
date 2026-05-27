"""
Query Router Agent
Hybrid intent classifier:

  1. **Weighted keyword scoring** (fast path). Each agent owns a list of
     ``(pattern, weight)`` rules; the highest scorer above ``MIN_SCORE``
     wins. Strong intent-specific phrases get high weight; common verbs
     like "explain" or polite sign-offs like "thank you" get low weight
     so they no longer dominate the classification on their own.
  2. **Semantic fallback** (slow path). When no agent crosses
     ``MIN_SCORE`` we ask the embedding-based ``semantic_router`` so
     paraphrased queries that share no vocabulary with the keyword rules
     still route correctly. Disabled with ``SEMANTIC_ROUTER_ENABLED=0``.

Routing decisions are logged to Neo4j via ``graph_ops.log_query``.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, Tuple

from backend.agents.state import AgentState
from backend.agents import graph_ops

logger = logging.getLogger(__name__)

# Allow ops to toggle semantic routing off entirely without a redeploy.
_SEMANTIC_ROUTER_ENABLED = os.environ.get("SEMANTIC_ROUTER_ENABLED", "1") != "0"

# ── Weighted intent signals ──────────────────────────────────────
# Each rule lists (agent, reason, [(pattern, weight), ...]). The router scores
# every agent against the query and picks the highest scorer above MIN_SCORE.
# Strong, intent-specific phrases get high weight; common verbs like "explain"
# or polite sign-offs like "thank you" get low weight so they no longer
# dominate the classification on their own.

MIN_SCORE = 2  # below this the query is treated as general tutoring

_SIGNALS: list[tuple[str, str, list[tuple[str, int]]]] = [
    (
        "feedback_agent",
        "Detected feedback or opinion",
        [
            (r"\b(feedback|suggestion|complaint|compliment)\b", 4),
            (r"\b(love this|hate this|terrible|awesome|amazing)\b", 4),
            (r"\b(issue with the (app|platform|product)|the platform|this app)\b", 3),
            (r"\b(satisfied|disappointed|improve)\b", 2),
            # Polite sign-offs alone are NOT enough — weight 1 so they only
            # tip the scale when combined with a stronger signal.
            (r"\b(thanks?( you)?)\b", 1),
        ],
    ),
    (
        "quiz_helper_agent",
        "Detected quiz-related query",
        [
            (r"\b(quiz|exam|assessment|test result|my results|my grades)\b", 5),
            (r"\b(weak topic|strong topic|study plan|how did i do)\b", 4),
            (r"\b(my (score|performance)|review (my )?(quiz|results))\b", 4),
            (r"\bwhat should i study\b", 3),
        ],
    ),
    (
        "doubts_agent",
        "Detected confusion or doubt",
        [
            (r"\b(don'?t understand|doubt|unclear|i'?m lost|makes no sense)\b", 4),
            (r"\b(can you clarify|stuck on|struggling with|help me understand)\b", 3),
            (r"\bdifference between\b|\bwhat does\b.+\bmean\b", 3),
            (r"\bconfused\b", 2),
        ],
    ),
    (
        "personalised_agent",
        "Detected request for personalised explanation",
        [
            (r"\b(in simple terms|eli5|like i'?m (five|5)|step by step)\b", 4),
            (r"\b(analogy|relate to|connect to what i know|tailor|my level)\b", 3),
            (r"\b(walk me through|teach me|break (it|this) down)\b", 3),
            # "explain" is the single most common verb in tutoring; on its own
            # it shouldn't beat a clearer signal.
            (r"\bexplain\b", 1),
        ],
    ),
]


def _extract_user_question(text: str) -> str:
    """Extract the original user question from context-enriched queries.

    The chat route prepends document context or style instructions before the
    actual user question with markers like 'User question: ...'.  We classify
    only the user's intent — not the document content — to avoid misrouting.
    """
    marker = "User question:"
    idx = text.rfind(marker)
    if idx != -1:
        return text[idx + len(marker):].strip()
    return text


def _score_agent(text: str, patterns: list[tuple[str, int]]) -> int:
    return sum(weight for pattern, weight in patterns if re.search(pattern, text))


def classify_query(text: str) -> Tuple[str, str]:
    """Return ``(agent_name, route_reason)`` for the given query text.

    Two-stage classification:
      1. Weighted keyword scoring across all agents — winner must beat
         ``MIN_SCORE`` to be selected.
      2. If no agent crosses ``MIN_SCORE``, consult the embedding-based
         semantic router so queries that mix vocabularies (or paraphrase
         away from the keyword rules entirely) still route well.
    """
    user_q = _extract_user_question(text)
    lower = user_q.lower()

    best_agent = "tutor_agent"
    best_reason = "General tutoring query (default)"
    best_score = MIN_SCORE - 1

    for agent, reason, patterns in _SIGNALS:
        score = _score_agent(lower, patterns)
        if score > best_score:
            best_agent = agent
            best_reason = reason
            best_score = score

    logger.debug(
        "Router scoring: query=%r winner=%s score=%d", lower[:80], best_agent, best_score
    )

    # Keyword scoring was inconclusive — try semantic fallback before
    # settling on the generic tutor.
    if best_score < MIN_SCORE and _SEMANTIC_ROUTER_ENABLED:
        try:
            from backend.agents import semantic_router

            result = semantic_router.classify(user_q)
            if result is not None:
                agent, _sim, reason = result
                return agent, reason
        except Exception as exc:
            # Never let routing fail the request — keyword default is fine.
            logger.debug("Semantic router fallback skipped: %s", exc)

    return best_agent, best_reason


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
