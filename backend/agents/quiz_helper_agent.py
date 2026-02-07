"""
Quiz Helper Agent
Answers questions about quiz performance, weak/strong topics, and provides
personalised study recommendations based on PostgreSQL quiz_results + Neo4j.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.agents.state import AgentState
from backend.agents import graph_ops

logger = logging.getLogger(__name__)

_QUIZ_PROMPT = """\
You are a study advisor who helps students understand their quiz performance
and plan their next steps.

Student profile:
- Name: {student_name}
- Level: {student_level}
- Total quizzes taken: {total_quizzes}
- Recent average score: {recent_avg_score}%
- Strong topics: {top_topics}
- Weak topics: {weak_topics}
- Concepts they struggle with (from tutoring history): {struggled_concepts}

Quiz data summary:
{quiz_summary}

Instructions:
- Answer the student's question about their quiz performance.
- Be encouraging but honest about areas for improvement.
- Provide specific, actionable study recommendations.
- If they ask "what should I study next?", prioritise weak topics and struggled concepts.
- If they ask about scores, present the data clearly with context.

Student question: {query}
"""


def _build_quiz_summary(username: str) -> str:
    """Fetch recent quiz results from PostgreSQL for the prompt."""
    try:
        from backend.services import get_storage_backend

        storage = get_storage_backend()
        pg = getattr(storage, "postgres", storage)
        cursor_ctx = getattr(pg, "_get_cursor", None)
        if cursor_ctx is None:
            return "Quiz data not available."

        with cursor_ctx() as cursor:
            cursor.execute(
                """
                SELECT quiz_id, score, total_questions,
                       ROUND(score::numeric / NULLIF(total_questions, 0) * 100, 1) AS pct,
                       created_at
                FROM quiz_results
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (username,),
            )
            rows = cursor.fetchall()
            if not rows:
                return "No quiz attempts recorded yet."

            lines = ["Recent quiz results (most recent first):"]
            for r in rows:
                date_str = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "?"
                lines.append(
                    f"  - {date_str}: {r['score']}/{r['total_questions']} "
                    f"({r['pct']}%)"
                )
            return "\n".join(lines)
    except Exception as exc:
        logger.warning("quiz summary fetch failed: %s", exc)
        return "Quiz data could not be retrieved."


def quiz_helper_agent(state: AgentState) -> Dict:
    """LangGraph node: quiz-based study advice."""
    from backend.llm_provider import get_llm

    query = state["input"]
    user_id = state.get("user_id", "")
    student_name = state.get("student_name", "Student")
    student_level = state.get("student_level", "intermediate")
    top_topics = state.get("top_topics", [])
    weak_topics = state.get("weak_topics", [])
    struggled = state.get("struggled_concepts", [])
    model_id = state.get("model_id")

    # Load profile numbers (already cached by profile.py)
    from backend.agents.profile import load_student_profile
    profile = load_student_profile(user_id)
    total_quizzes = profile.get("total_quizzes", 0)
    recent_avg = profile.get("recent_avg_score", 0)

    quiz_summary = _build_quiz_summary(user_id)

    prompt = _QUIZ_PROMPT.format(
        student_name=student_name,
        student_level=student_level,
        total_quizzes=total_quizzes,
        recent_avg_score=recent_avg,
        top_topics=", ".join(top_topics) if top_topics else "not determined",
        weak_topics=", ".join(weak_topics) if weak_topics else "not determined",
        struggled_concepts=", ".join(struggled) if struggled else "none recorded",
        quiz_summary=quiz_summary,
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
        logger.error("Quiz helper LLM call failed: %s", exc)
        response_text = (
            "I'm sorry, I couldn't generate study recommendations right now. "
            "Try asking about a specific topic you'd like to review."
        )

    return {"response": response_text, "agent": "quiz_helper_agent"}
