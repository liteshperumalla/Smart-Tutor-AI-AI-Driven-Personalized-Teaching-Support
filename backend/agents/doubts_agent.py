"""
Doubts Agent
Handles confusion or conceptual misunderstandings. Extracts the core concept,
checks if the student has struggled with it before, and provides step-by-step
resolution adapted to their level.
"""

from __future__ import annotations

import logging
import re
from typing import Dict

from backend.agents.state import AgentState
from backend.agents import graph_ops
from backend.agents.llm_utils import complete_with_model_fallback

logger = logging.getLogger(__name__)

_DOUBT_PROMPT = """\
You are a patient doubt-resolution tutor. A student is confused and needs help.

Student profile:
- Name: {student_name}
- Level: {student_level}
- Previously struggled with: {struggled_concepts}

Context from course materials:
{context}

{prior_note}

Instructions:
- Identify the core concept the student is confused about.
- Provide a clear, step-by-step explanation.
- Use simple language appropriate for a {student_level} student.
- Include a concrete example or analogy.
- End with a brief check: "Does this make sense? Feel free to ask follow-up questions."

Student's doubt: {query}
"""


def _extract_concept(query: str) -> str:
    """Best-effort extraction of the core concept from a doubt query."""
    # Remove common doubt preambles
    cleaned = re.sub(
        r"^(i (don'?t|do not) understand |i'?m confused about |"
        r"can you (clarify|explain) |what (is|are|does) )",
        "",
        query.lower().strip(),
    )
    # Take first meaningful phrase (up to 4 words)
    words = cleaned.split()[:4]
    return " ".join(words).strip("?.!, ") or "the topic"


def doubts_agent(state: AgentState) -> Dict:
    """LangGraph node: doubt resolution."""
    query = state["input"]
    context = state.get("context_str", "No additional context available.")
    student_name = state.get("student_name", "Student")
    student_level = state.get("student_level", "intermediate")
    struggled = state.get("struggled_concepts", [])
    model_id = state.get("model_id")

    concept = _extract_concept(query)

    # Check if student has struggled with this concept before
    prior_note = ""
    if any(concept.lower() in s.lower() for s in struggled):
        prior_note = (
            f"Note: The student has struggled with '{concept}' before. "
            "Build on what they might already partially understand, and try "
            "a different angle of explanation this time."
        )

    prompt = _DOUBT_PROMPT.format(
        student_name=student_name,
        student_level=student_level,
        struggled_concepts=", ".join(struggled) if struggled else "none recorded",
        context=context,
        prior_note=prior_note,
        query=query,
    )

    try:
        response_text = complete_with_model_fallback(
            prompt=prompt,
            logger=logger,
            model_id=model_id,
        )
    except Exception as exc:
        logger.error("Doubts LLM call failed: %s", exc)
        response_text = (
            "I'm sorry, I had trouble generating an explanation. "
            "Could you tell me more specifically what part confuses you?"
        )

    graph_ops.log_doubt(
        username=state.get("user_id", ""),
        concept=concept,
        response=response_text[:500],
        student_level=student_level,
    )

    return {"response": response_text, "agent": "doubts_agent"}
