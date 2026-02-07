"""
Neo4j Graph Write Operations
Each agent calls these helpers to log interactions into the knowledge graph.
All operations are non-blocking fire-and-forget to avoid slowing responses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_write(query: str, params: dict) -> None:
    """Execute a write query; swallow errors so agent responses are never blocked."""
    try:
        from backend.agents.neo4j_client import get_neo4j_client
        get_neo4j_client().execute_write(query, params)
    except Exception as exc:
        logger.warning("Neo4j write failed: %s", exc)


# ── Student node (upsert) ───────────────────────────────────────

def ensure_student(username: str, display_name: Optional[str] = None) -> None:
    _safe_write(
        "MERGE (s:Student {username: $username}) "
        "ON CREATE SET s.display_name = $display_name, s.created_at = $now, "
        "s.total_queries = 0, s.total_tutoring_sessions = 0, "
        "s.total_doubts = 0, s.total_feedback = 0 "
        "SET s.last_active = $now",
        {"username": username, "display_name": display_name or username, "now": _now_iso()},
    )


# ── Query logging (used by router) ──────────────────────────────

def log_query(username: str, text: str, query_type: str) -> None:
    ensure_student(username)
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "CREATE (q:Query {text: $text, query_type: $query_type, timestamp: $ts}) "
        "CREATE (s)-[:ASKED]->(q) "
        "SET s.total_queries = COALESCE(s.total_queries, 0) + 1",
        {"username": username, "text": text, "query_type": query_type, "ts": _now_iso()},
    )


# ── Tutor agent ──────────────────────────────────────────────────

def log_tutoring_session(
    username: str, query: str, response: str, session_type: str, student_level: str, topics: List[str]
) -> None:
    ensure_student(username)
    ts = _now_iso()
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "CREATE (sess:TutoringSession {query: $query, response: $response, "
        "session_type: $session_type, student_level: $student_level, timestamp: $ts}) "
        "CREATE (s)-[:HAD_TUTORING_SESSION]->(sess) "
        "SET s.total_tutoring_sessions = COALESCE(s.total_tutoring_sessions, 0) + 1",
        {
            "username": username, "query": query, "response": response,
            "session_type": session_type, "student_level": student_level, "ts": ts,
        },
    )
    for topic in topics:
        _safe_write(
            "MATCH (s:Student {username: $username}) "
            "MERGE (t:Topic {name: $topic}) "
            "ON CREATE SET t.last_tutored = $ts "
            "SET t.last_tutored = $ts "
            "MERGE (s)-[r:STUDIED]->(t) "
            "ON CREATE SET r.study_count = 1, r.last_study = $ts "
            "ON MATCH SET r.study_count = r.study_count + 1, r.last_study = $ts",
            {"username": username, "topic": topic.lower().strip(), "ts": ts},
        )


# ── Doubts agent ─────────────────────────────────────────────────

def log_doubt(username: str, concept: str, response: str, student_level: str) -> None:
    ensure_student(username)
    ts = _now_iso()
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "MERGE (c:Concept {name: $concept}) "
        "ON CREATE SET c.last_questioned = $ts "
        "SET c.last_questioned = $ts "
        "CREATE (d:Doubt {concept: $concept, response: $response, "
        "student_level: $student_level, timestamp: $ts}) "
        "CREATE (s)-[:RECEIVED_DOUBT_RESOLUTION]->(d) "
        "CREATE (d)-[:ADDRESSES]->(c) "
        "MERGE (s)-[:HAS_DOUBT]->(c) "
        "MERGE (s)-[:STRUGGLES_WITH]->(c) "
        "SET s.total_doubts = COALESCE(s.total_doubts, 0) + 1",
        {"username": username, "concept": concept.lower().strip(), "response": response,
         "student_level": student_level, "ts": ts},
    )


# ── Personalised agent ──────────────────────────────────────────

def log_explanation(username: str, query: str, explanation: str, level: str) -> None:
    ensure_student(username)
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "CREATE (e:Explanation {query: $query, explanation: $explanation, "
        "level: $level, timestamp: $ts}) "
        "CREATE (s)-[:RECEIVED_EXPLANATION]->(e)",
        {"username": username, "query": query, "explanation": explanation, "level": level, "ts": _now_iso()},
    )


# ── Quiz helper agent ───────────────────────────────────────────

def log_quiz_attempt(
    username: str, quiz_id: str, score: float, percentage: float, folders: List[str]
) -> None:
    ensure_student(username)
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "CREATE (qa:QuizAttempt {quiz_id: $quiz_id, score: $score, "
        "percentage: $percentage, folders: $folders, timestamp: $ts}) "
        "CREATE (s)-[:ATTEMPTED_QUIZ]->(qa)",
        {"username": username, "quiz_id": quiz_id, "score": score,
         "percentage": percentage, "folders": folders, "ts": _now_iso()},
    )


# ── Feedback agent ───────────────────────────────────────────────

def log_feedback(username: str, text: str, sentiment: str, category: str) -> None:
    ensure_student(username)
    _safe_write(
        "MATCH (s:Student {username: $username}) "
        "CREATE (f:Feedback {text: $text, sentiment: $sentiment, "
        "category: $category, timestamp: $ts}) "
        "CREATE (s)-[:GAVE_FEEDBACK]->(f) "
        "SET s.total_feedback = COALESCE(s.total_feedback, 0) + 1",
        {"username": username, "text": text, "sentiment": sentiment,
         "category": category, "ts": _now_iso()},
    )
