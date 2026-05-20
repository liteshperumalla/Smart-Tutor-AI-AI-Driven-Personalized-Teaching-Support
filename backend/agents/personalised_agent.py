"""
Personalised Agent
Provides level-adapted explanations that connect new concepts to topics
the student already knows (from quiz history and Neo4j study patterns).
"""

from __future__ import annotations

import logging
from typing import Dict

from backend.agents.state import AgentState
from backend.agents import graph_ops
from backend.agents.llm_utils import complete_with_model_fallback

logger = logging.getLogger(__name__)

_PERSONALISED_PROMPT = """\
You are a personalisation-focused tutor who adapts explanations to each student.

Student profile:
- Name: {student_name}
- Level: {student_level}
- Topics they know well: {top_topics}
- Topics they find difficult: {weak_topics}
- Recently studied: {recently_studied}

Context from course materials:
{context}

Instructions:
- Explain the topic at the {student_level} level.
- Connect new ideas to topics the student already knows ({top_topics_inline}).
- Use analogies based on their familiar topics when possible.
  For example: "Since you've studied {example_topic}, think of this like..."
- If the topic overlaps with their weak areas, be extra patient and detailed.
- Structure: brief overview, then deeper explanation, then a connecting summary.

Student's request: {query}
"""


def _build_personalised_prompt(state: AgentState) -> str:
    top_topics = state.get("top_topics", []) or []
    weak_topics = state.get("weak_topics", []) or []
    recently_studied = state.get("recently_studied", []) or []
    example_topic = top_topics[0] if top_topics else "a familiar concept"
    top_inline = ", ".join(top_topics) if top_topics else "their existing knowledge"

    return _PERSONALISED_PROMPT.format(
        student_name=state.get("student_name", "Student"),
        student_level=state.get("student_level", "intermediate"),
        top_topics=", ".join(top_topics) if top_topics else "not yet determined",
        weak_topics=", ".join(weak_topics) if weak_topics else "not yet determined",
        recently_studied=", ".join(recently_studied) if recently_studied else "none yet",
        context=state.get("context_str", "No additional context available."),
        query=state["input"],
        top_topics_inline=top_inline,
        example_topic=example_topic,
    )


def prepare_personalised(state: AgentState) -> Dict:
    """Streaming-pipeline hook."""
    return {
        "prompt": _build_personalised_prompt(state),
        "model_id": state.get("model_id"),
        "agent": "personalised_agent",
    }


def finalize_personalised(state: AgentState, response_text: str) -> None:
    graph_ops.log_explanation(
        username=state.get("user_id", ""),
        query=state["input"],
        explanation=response_text[:500],
        level=state.get("student_level", "intermediate"),
    )


def personalised_agent(state: AgentState) -> Dict:
    """LangGraph node: personalised explanation."""
    query = state["input"]
    context = state.get("context_str", "No additional context available.")
    student_name = state.get("student_name", "Student")
    student_level = state.get("student_level", "intermediate")
    top_topics = state.get("top_topics", [])
    weak_topics = state.get("weak_topics", [])
    recently_studied = state.get("recently_studied", [])
    model_id = state.get("model_id")

    example_topic = top_topics[0] if top_topics else "a familiar concept"
    top_inline = ", ".join(top_topics) if top_topics else "their existing knowledge"

    prompt = _PERSONALISED_PROMPT.format(
        student_name=student_name,
        student_level=student_level,
        top_topics=", ".join(top_topics) if top_topics else "not yet determined",
        weak_topics=", ".join(weak_topics) if weak_topics else "not yet determined",
        recently_studied=", ".join(recently_studied) if recently_studied else "none yet",
        context=context,
        query=query,
        top_topics_inline=top_inline,
        example_topic=example_topic,
    )

    try:
        response_text = complete_with_model_fallback(
            prompt=prompt,
            logger=logger,
            model_id=model_id,
        )
    except Exception as exc:
        logger.error("Personalised LLM call failed: %s", exc)
        response_text = (
            "I'm sorry, I had trouble generating a personalised explanation. "
            "Let me try a standard approach instead. Could you rephrase what you'd like explained?"
        )

    graph_ops.log_explanation(
        username=state.get("user_id", ""),
        query=query,
        explanation=response_text[:500],
        level=student_level,
    )

    return {"response": response_text, "agent": "personalised_agent"}
