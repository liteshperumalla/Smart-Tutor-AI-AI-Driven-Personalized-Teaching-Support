"""
Student Profile Builder
Derives a student profile from two sources:
  1. PostgreSQL quiz_results table (performance level, topics, scores)
  2. Neo4j knowledge graph (struggled concepts, study patterns, feedback)
Results are cached in Redis with a 600s TTL.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.config import config

logger = logging.getLogger(__name__)

# ── Performance level thresholds ─────────────────────────────────
_LEVEL_THRESHOLDS = {"advanced": 80, "intermediate": 50}

_GENERIC_NAME_TOKENS = {
    "admin",
    "administrator",
    "student",
    "user",
    "google",
    "mail",
    "gmail",
    "yahoo",
    "outlook",
    "hotmail",
    "icloud",
}


def _compute_level(avg_pct: float) -> str:
    if avg_pct >= _LEVEL_THRESHOLDS["advanced"]:
        return "advanced"
    if avg_pct >= _LEVEL_THRESHOLDS["intermediate"]:
        return "intermediate"
    return "beginner"


def _clean_name_candidate(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (value or "").strip()))


def _humanize_identifier(value: str) -> str:
    text = _clean_name_candidate(value)
    if not text:
        return ""
    text = text.split("@", 1)[0]
    text = re.sub(r"[_\-.]+", " ", text)
    parts = []
    for token in text.split():
        if not token:
            continue
        if token.lower() in _GENERIC_NAME_TOKENS and len(text.split()) == 1:
            continue
        if token.isdigit():
            continue
        parts.append(token)
    if not parts:
        return ""
    return " ".join(parts[:3]).title()


def resolve_student_display_name(username: str, display_name: Optional[str] = None) -> str:
    explicit_display_name = _clean_name_candidate(display_name)
    if explicit_display_name and not _looks_like_email(explicit_display_name):
        return explicit_display_name

    user_record: Dict[str, Any] = {}
    try:
        from backend.database import get_user_db

        user_record = get_user_db().get_user_safe(username) or {}
    except Exception:
        user_record = {}

    for candidate in (
        user_record.get("display_name"),
        user_record.get("full_name"),
        explicit_display_name,
    ):
        cleaned = _clean_name_candidate(candidate)
        if cleaned and not _looks_like_email(cleaned):
            return cleaned

    for candidate in (
        user_record.get("username"),
        username,
        user_record.get("email"),
    ):
        fallback = _humanize_identifier(candidate or "")
        if fallback:
            return fallback

    return "Student"


# ── PostgreSQL queries ───────────────────────────────────────────

def _quiz_profile(username: str) -> Dict[str, Any]:
    """Fetch quiz-based profile from PostgreSQL."""
    try:
        from backend.services import get_storage_backend

        storage = get_storage_backend()
        pg = getattr(storage, "postgres", storage)
        cursor_ctx = getattr(pg, "_get_cursor", None)
        if cursor_ctx is None:
            return {}

        with cursor_ctx() as cursor:
            # Average score percentage
            cursor.execute(
                """
                SELECT
                    COUNT(*)                                           AS total_quizzes,
                    COALESCE(AVG(score::float / NULLIF(total_questions, 0) * 100), 0) AS avg_pct
                FROM quiz_results
                WHERE username = %s AND total_questions > 0
                """,
                (username,),
            )
            row = cursor.fetchone()
            total_quizzes = row["total_quizzes"] if row else 0
            avg_pct = float(row["avg_pct"]) if row else 0

            # Top topics (most-taken folders)
            cursor.execute(
                """
                SELECT
                    jsonb_array_elements_text(metadata->'selected_folders') AS folder,
                    COUNT(*) AS cnt
                FROM quiz_results
                WHERE username = %s AND metadata ? 'selected_folders'
                GROUP BY folder
                ORDER BY cnt DESC
                LIMIT 5
                """,
                (username,),
            )
            top_topics = [r["folder"] for r in cursor.fetchall()]

            # Weak topics (lowest avg scores)
            cursor.execute(
                """
                SELECT
                    folder,
                    AVG(score::float / NULLIF(total_questions, 0) * 100) AS avg_score
                FROM (
                    SELECT
                        jsonb_array_elements_text(metadata->'selected_folders') AS folder,
                        score, total_questions
                    FROM quiz_results
                    WHERE username = %s AND metadata ? 'selected_folders' AND total_questions > 0
                ) sub
                GROUP BY folder
                ORDER BY avg_score ASC
                LIMIT 3
                """,
                (username,),
            )
            weak_topics = [r["folder"] for r in cursor.fetchall()]

        return {
            "total_quizzes": total_quizzes,
            "recent_avg_score": round(avg_pct, 1),
            "performance_level": _compute_level(avg_pct),
            "top_topics": top_topics,
            "weak_topics": weak_topics,
        }
    except Exception as exc:
        logger.warning("quiz_profile failed for %s: %s", username, exc)
        return {}


# ── Neo4j queries ────────────────────────────────────────────────

def _graph_profile(username: str) -> Dict[str, Any]:
    """Fetch graph-based profile from Neo4j (READ only)."""
    try:
        from backend.agents.neo4j_client import get_neo4j_client

        client = get_neo4j_client()

        struggled = client.execute_read(
            "MATCH (s:Student {username: $username})-[:STRUGGLES_WITH]->(c:Concept) "
            "RETURN c.name AS name ORDER BY c.last_questioned DESC LIMIT 5",
            {"username": username},
        )

        studied = client.execute_read(
            "MATCH (s:Student {username: $username})-[r:STUDIED]->(t:Topic) "
            "RETURN t.name AS name, r.study_count AS cnt ORDER BY r.last_study DESC LIMIT 10",
            {"username": username},
        )

        feedback = client.execute_read(
            "MATCH (s:Student {username: $username})-[:GAVE_FEEDBACK]->(f:Feedback) "
            "RETURN f.sentiment AS sentiment, COUNT(*) AS count",
            {"username": username},
        )

        interaction_counts = client.execute_read(
            "MATCH (s:Student {username: $username}) "
            "RETURN s.total_queries AS tq, s.total_tutoring_sessions AS ts, "
            "s.total_doubts AS td, s.total_feedback AS tf",
            {"username": username},
        )

        ic = interaction_counts[0] if interaction_counts else {}
        total = sum(v or 0 for v in [ic.get("tq"), ic.get("ts"), ic.get("td"), ic.get("tf")])

        return {
            "struggled_concepts": [r["name"] for r in struggled],
            "recently_studied": [r["name"] for r in studied],
            "feedback_sentiment": {r["sentiment"]: r["count"] for r in feedback},
            "total_interactions": total,
        }
    except Exception as exc:
        logger.warning("graph_profile failed for %s: %s", username, exc)
        return {}


# ── Public API ───────────────────────────────────────────────────

def load_student_profile(username: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Build a combined student profile, cached in Redis for 600s."""
    resolved_display_name = resolve_student_display_name(username, display_name)

    # Try Redis cache first
    cache_key = f"student_profile:{username}"
    cached = _redis_get(cache_key)
    if cached is not None:
        cached["display_name"] = resolved_display_name
        return cached

    quiz = _quiz_profile(username)
    graph = _graph_profile(username)

    profile: Dict[str, Any] = {
        "display_name": resolved_display_name,
        "performance_level": quiz.get("performance_level", config.AGENT_DEFAULT_LEVEL),
        "top_topics": quiz.get("top_topics", []),
        "weak_topics": quiz.get("weak_topics", []),
        "total_quizzes": quiz.get("total_quizzes", 0),
        "recent_avg_score": quiz.get("recent_avg_score", 0),
        "struggled_concepts": graph.get("struggled_concepts", []),
        "recently_studied": graph.get("recently_studied", []),
        "feedback_sentiment": graph.get("feedback_sentiment", {}),
        "total_interactions": graph.get("total_interactions", 0),
    }

    _redis_set(cache_key, profile, ttl=600)
    return profile


# ── Redis helpers ────────────────────────────────────────────────

def _redis_get(key: str) -> Optional[Dict[str, Any]]:
    try:
        import redis as redis_lib

        r = redis_lib.Redis(
            host=config.REDIS_HOST, port=config.REDIS_PORT,
            db=config.REDIS_DB, decode_responses=True,
        )
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _redis_set(key: str, value: Dict[str, Any], ttl: int = 600) -> None:
    try:
        import redis as redis_lib

        r = redis_lib.Redis(
            host=config.REDIS_HOST, port=config.REDIS_PORT,
            db=config.REDIS_DB, decode_responses=True,
        )
        r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass
