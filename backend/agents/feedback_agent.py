"""
Feedback Agent
Performs keyword-based sentiment analysis and categorises user feedback.
Logs results to Neo4j and provides a human-friendly acknowledgement.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Tuple

from backend.agents.state import AgentState
from backend.agents import graph_ops

logger = logging.getLogger(__name__)

# ── Sentiment keywords ───────────────────────────────────────────

_POSITIVE = {
    "great", "love", "awesome", "excellent", "amazing", "helpful",
    "fantastic", "wonderful", "good", "nice", "thank", "thanks",
    "appreciate", "impressed", "satisfied", "perfect", "best",
}
_NEGATIVE = {
    "bad", "terrible", "hate", "awful", "horrible", "poor",
    "disappointed", "frustrated", "annoying", "broken", "slow",
    "useless", "worst", "complaint", "issue", "bug",
}

# ── Categories ───────────────────────────────────────────────────

_CATEGORY_PATTERNS = [
    ("ui_ux", r"\b(ui|ux|interface|design|layout|button|page|navigation|dark mode|theme)\b"),
    ("performance", r"\b(slow|fast|speed|loading|lag|timeout|performance)\b"),
    ("content", r"\b(content|material|course|lecture|quiz|question|explanation)\b"),
    ("feature_request", r"\b(feature|add|wish|should|could you|would be nice|missing)\b"),
    ("bug_report", r"\b(bug|broken|error|crash|not working|doesn'?t work|glitch)\b"),
]


def _analyse_sentiment(text: str) -> str:
    lower = text.lower()
    words = set(re.findall(r"[a-z]+", lower))
    pos = len(words & _POSITIVE)
    neg = len(words & _NEGATIVE)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _categorise(text: str) -> str:
    lower = text.lower()
    for category, pattern in _CATEGORY_PATTERNS:
        if re.search(pattern, lower):
            return category
    return "general"


_RESPONSES = {
    "positive": (
        "Thank you so much for your kind feedback! It really motivates us "
        "to keep improving the platform. If there's anything specific you'd "
        "like to see added, feel free to let us know!"
    ),
    "negative": (
        "I'm sorry to hear about your experience. Your feedback is valuable "
        "and we'll work on addressing the issues you've raised. Could you "
        "share more details so we can improve?"
    ),
    "neutral": (
        "Thank you for sharing your thoughts! We appreciate all feedback "
        "as it helps us make the platform better for everyone."
    ),
}


def feedback_agent(state: AgentState) -> Dict:
    """LangGraph node: sentiment analysis + acknowledgement."""
    query = state["input"]
    user_id = state.get("user_id", "")

    sentiment = _analyse_sentiment(query)
    category = _categorise(query)
    response_text = _RESPONSES[sentiment]

    # Check feedback history for trend
    try:
        from backend.agents.neo4j_client import get_neo4j_client
        client = get_neo4j_client()
        history = client.execute_read(
            "MATCH (s:Student {username: $username})-[:GAVE_FEEDBACK]->(f:Feedback) "
            "RETURN f.sentiment AS s ORDER BY f.timestamp DESC LIMIT 5",
            {"username": user_id},
        )
        if history and sentiment == "positive":
            recent_positive = sum(1 for h in history if h.get("s") == "positive")
            if recent_positive >= 2:
                response_text += (
                    "\n\nWe notice you've been consistently happy with the platform "
                    "- that's wonderful to hear!"
                )
    except Exception:
        pass  # trend check is best-effort

    graph_ops.log_feedback(
        username=user_id,
        text=query[:500],
        sentiment=sentiment,
        category=category,
    )

    return {
        "response": response_text,
        "agent": "feedback_agent",
        "feedback_recorded": True,
        "sentiment": sentiment,
    }
