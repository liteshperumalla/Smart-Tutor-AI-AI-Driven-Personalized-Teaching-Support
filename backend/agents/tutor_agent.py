"""
Tutor Agent
General-purpose tutoring with RAG context. Adapts difficulty to student level
and avoids repeating topics the student has recently studied.
"""

from __future__ import annotations

import logging
import re
from typing import Dict

from backend.agents.state import AgentState
from backend.agents import graph_ops

logger = logging.getLogger(__name__)

_TUTOR_PROMPT = """\
You are a friendly and knowledgeable AI tutor for university students.

Student profile:
- Name: {student_name}
- Level: {student_level}
- Recently studied topics: {recently_studied}

Context from course materials:
{context}

Instructions:
- Answer the student's question using the context provided.
- Adapt your explanation depth to the student's level ({student_level}).
- If the student recently studied a related topic, briefly connect to it.
- Write in a natural, flowing style without section headings like "Concise Answer" or "Elaboration".
- Include citations like [Source 1] when referencing context.
- If you greet the student, use a natural human name only. Never greet them with an email address or technical identifier.

Student question: {query}
"""


def _extract_topics(query: str) -> list[str]:
    """Extract probable topic keywords from the query."""
    stop = {"what", "how", "why", "the", "is", "are", "can", "does", "do", "a", "an", "in", "of", "for", "to", "and", "or", "me", "about", "this", "that", "i"}
    words = re.findall(r"[a-z]+", query.lower())
    return [w for w in words if w not in stop and len(w) > 2][:5]


def tutor_agent(state: AgentState) -> Dict:
    """LangGraph node: general tutoring with RAG."""
    from backend.llm_provider import get_llm

    query = state["input"]
    context = state.get("context_str", "No additional context available.")
    student_name = state.get("student_name", "Student")
    student_level = state.get("student_level", "intermediate")
    recently_studied = state.get("recently_studied", [])
    model_id = state.get("model_id")

    prompt = _TUTOR_PROMPT.format(
        student_name=student_name,
        student_level=student_level,
        recently_studied=", ".join(recently_studied) if recently_studied else "none yet",
        context=context,
        query=query,
    )

    llm_kwargs = {}
    if model_id:
        llm_kwargs["model_id"] = model_id
    llm = get_llm(**llm_kwargs)

    try:
        response = llm.complete(prompt)
        response_text = str(response)
    except Exception as exc:
        logger.error("Tutor LLM call failed: %s", exc)
        response_text = (
            "I'm sorry, I encountered an issue generating a response. "
            "Could you try rephrasing your question?"
        )

    topics = _extract_topics(query)
    graph_ops.log_tutoring_session(
        username=state.get("user_id", ""),
        query=query,
        response=response_text[:500],
        session_type="general",
        student_level=student_level,
        topics=topics,
    )

    return {"response": response_text, "agent": "tutor_agent"}
