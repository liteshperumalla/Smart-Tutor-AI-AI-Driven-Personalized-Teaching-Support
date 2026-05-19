"""
Admin Service
Business logic for admin operations: user management, feedback aggregation,
announcements CRUD, and dashboard statistics.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.database import get_user_db
from backend.logger import get_logger
from backend.services.appointment_service import AppointmentService

logger = get_logger(__name__)

ANNOUNCEMENTS_FILE = os.path.join(
    getattr(config, "DATA_DIR", "data"), "announcements.json"
)


def _ensure_announcements_file() -> None:
    os.makedirs(os.path.dirname(ANNOUNCEMENTS_FILE), exist_ok=True)
    if not os.path.exists(ANNOUNCEMENTS_FILE):
        with open(ANNOUNCEMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


_file_lock = threading.Lock()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class AdminService:
    """Centralised admin business logic."""

    def __init__(self) -> None:
        self.user_db = get_user_db()
        self.user_data_root = Path(config.USER_DATA_ROOT)
        self.appointments = AppointmentService()
        _ensure_announcements_file()

    # ── User Management ──────────────────────────────────────────

    def list_users(self) -> List[Dict[str, Any]]:
        users = self.user_db.list_users() or []
        normalized_users: List[Dict[str, Any]] = []

        for user in users:
            if not isinstance(user, dict):
                continue
            normalized_users.append(
                {
                    **user,
                    "username": str(user.get("username") or user.get("email") or "Unknown user"),
                    "email": str(user.get("email") or ""),
                    "role": str(user.get("role") or "User"),
                }
            )

        return normalized_users

    def update_user_role(self, username: str, new_role: str) -> Dict[str, Any]:
        if new_role not in ("User", "Admin"):
            raise ValueError("Role must be 'User' or 'Admin'")
        # Role is stored in metadata JSONB for PostgreSQL backend
        return self.user_db.update_user(username, {"role": new_role})

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self.user_db.get_user(username)

    def delete_user(self, username: str) -> bool:
        return self.user_db.delete_user(username)

    # ── Feedback Aggregation ─────────────────────────────────────

    def get_all_feedback(
        self,
        feedback_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Scan feedback, bug reports, and message reports across all users."""
        entries: List[Dict[str, Any]] = []

        if not self.user_data_root.exists():
            return entries

        for user_dir in self.user_data_root.iterdir():
            if not user_dir.is_dir():
                continue
            fb_dir = user_dir / "feedback"

            username = user_dir.name

            if fb_dir.exists():
                for jsonl_file in fb_dir.glob("*.jsonl"):
                    kind = jsonl_file.stem  # "feedback" or "bug"
                    if feedback_type and kind != feedback_type:
                        continue
                    try:
                        with jsonl_file.open("r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    entry = json.loads(line)
                                    entry["username"] = username
                                    entry["type"] = kind
                                    # Generate a deterministic ID for status tracking
                                    entry.setdefault(
                                        "id",
                                        str(
                                            uuid.uuid5(
                                                uuid.NAMESPACE_DNS,
                                                f"{username}:{kind}:{entry.get('created_at', '')}:{entry.get('message', entry.get('description', ''))}",
                                            )
                                        ),
                                    )
                                    entry.setdefault("status", "new")
                                    entries.append(entry)
                                except json.JSONDecodeError:
                                    continue
                    except OSError:
                        continue

            if feedback_type not in (None, "report"):
                continue

            message_feedback_file = user_dir / "message_feedback" / "feedback.jsonl"
            if not message_feedback_file.exists():
                continue

            try:
                with message_feedback_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if entry.get("feedback_type") != "report":
                            continue

                        reason = entry.get("reason")
                        report_entry = {
                            "id": str(
                                uuid.uuid5(
                                    uuid.NAMESPACE_DNS,
                                    (
                                        f"{username}:report:{entry.get('session_id', '')}:"
                                        f"{entry.get('message_index', '')}:{entry.get('created_at', '')}:"
                                        f"{reason or ''}"
                                    ),
                                )
                            ),
                            "username": username,
                            "type": "report",
                            "status": "new",
                            "created_at": entry.get("created_at", ""),
                            "reason": reason,
                            "message": reason,
                            "session_id": str(entry.get("session_id") or ""),
                            "message_index": _coerce_int(entry.get("message_index")),
                        }
                        entries.append(report_entry)
            except OSError:
                continue

        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        return entries[:limit]

    def update_feedback_status(
        self, feedback_id: str, new_status: str
    ) -> Optional[Dict[str, Any]]:
        """Update the status of a feedback entry stored in the status overlay file."""
        feedback_exists = any(
            entry.get("id") == feedback_id for entry in self.get_all_feedback(limit=10000)
        )
        if not feedback_exists:
            return None
        statuses = self._load_feedback_statuses()
        statuses[feedback_id] = {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_feedback_statuses(statuses)
        return statuses[feedback_id]

    def _feedback_status_path(self) -> Path:
        return Path(
            getattr(config, "DATA_DIR", "data")
        ) / "feedback_statuses.json"

    def _load_feedback_statuses(self) -> Dict[str, Any]:
        path = self._feedback_status_path()
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_feedback_statuses(self, statuses: Dict[str, Any]) -> None:
        path = self._feedback_status_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(statuses, f, indent=2)

    def _summarize_message_feedback(self) -> Dict[str, int]:
        summary = {
            "thumbs_up": 0,
            "thumbs_down": 0,
            "report": 0,
        }
        if not self.user_data_root.exists():
            return summary

        for user_dir in self.user_data_root.iterdir():
            if not user_dir.is_dir():
                continue
            feedback_file = user_dir / "message_feedback" / "feedback.jsonl"
            if not feedback_file.exists():
                continue
            try:
                with feedback_file.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        feedback_type = entry.get("feedback_type")
                        if feedback_type in summary:
                            summary[feedback_type] += 1
            except OSError:
                continue
        return summary

    def _count_share_actions(self) -> int:
        total = 0
        if not self.user_data_root.exists():
            return total

        for user_dir in self.user_data_root.iterdir():
            if not user_dir.is_dir():
                continue
            share_file = user_dir / "share_history" / "shares.jsonl"
            if not share_file.exists():
                continue
            try:
                with share_file.open("r", encoding="utf-8") as handle:
                    total += sum(1 for line in handle if line.strip())
            except OSError:
                continue
        return total

    # ── Announcements CRUD ───────────────────────────────────────

    def _read_announcements(self) -> List[Dict[str, Any]]:
        _ensure_announcements_file()
        with _file_lock:
            with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        return data if isinstance(data, list) else []

    def _write_announcements(self, announcements: List[Dict[str, Any]]) -> None:
        _ensure_announcements_file()
        with _file_lock:
            tmp = ANNOUNCEMENTS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(announcements, f, indent=2, ensure_ascii=False)
            os.replace(tmp, ANNOUNCEMENTS_FILE)

    def list_announcements(self) -> List[Dict[str, Any]]:
        return self._read_announcements()

    def list_active_announcements(self) -> List[Dict[str, Any]]:
        return [a for a in self._read_announcements() if a.get("active", True)]

    def create_announcement(
        self,
        title: str,
        content: str,
        priority: str = "info",
        author: str = "admin",
    ) -> Dict[str, Any]:
        announcement = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "priority": priority,
            "author": author,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        announcements = self._read_announcements()
        announcements.insert(0, announcement)
        self._write_announcements(announcements)
        logger.info(f"Announcement created: {announcement['id']}")
        return announcement

    def update_announcement(
        self, announcement_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        announcements = self._read_announcements()
        for ann in announcements:
            if ann["id"] == announcement_id:
                allowed = {"title", "content", "priority", "active"}
                for key in allowed:
                    if key in updates:
                        ann[key] = updates[key]
                ann["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_announcements(announcements)
                logger.info(f"Announcement updated: {announcement_id}")
                return ann
        return None

    def delete_announcement(self, announcement_id: str) -> bool:
        announcements = self._read_announcements()
        filtered = [a for a in announcements if a["id"] != announcement_id]
        if len(filtered) == len(announcements):
            return False
        self._write_announcements(filtered)
        logger.info(f"Announcement deleted: {announcement_id}")
        return True

    # ── Quiz Metrics ──────────────────────────────────────────────

    def get_quiz_metrics(self) -> Dict[str, Any]:
        """Aggregate quiz metrics across all users from PostgreSQL."""
        try:
            from backend.services import get_storage_backend

            storage = get_storage_backend()
            # Get the postgres backend (may be direct or via hybrid)
            pg = getattr(storage, "postgres", storage)
            cursor_ctx = getattr(pg, "_get_cursor", None)
            if cursor_ctx is None:
                return {"error": "PostgreSQL backend not available"}

            with cursor_ctx() as cursor:
                # Overall stats
                cursor.execute("""
                    SELECT
                        COUNT(*) AS total_quizzes,
                        COUNT(DISTINCT username) AS unique_users,
                        COALESCE(AVG(score::float / NULLIF(total_questions, 0) * 100), 0) AS avg_percentage,
                        COALESCE(MAX(score::float / NULLIF(total_questions, 0) * 100), 0) AS highest_percentage,
                        COALESCE(MIN(score::float / NULLIF(total_questions, 0) * 100), 0) AS lowest_percentage,
                        SUM(total_questions) AS total_questions_answered
                    FROM quiz_results
                """)
                stats_row = cursor.fetchone()

                # Score distribution (buckets: 0-20, 20-40, 40-60, 60-80, 80-100)
                cursor.execute("""
                    SELECT
                        CASE
                            WHEN score::float / NULLIF(total_questions, 0) * 100 >= 80 THEN '80-100'
                            WHEN score::float / NULLIF(total_questions, 0) * 100 >= 60 THEN '60-80'
                            WHEN score::float / NULLIF(total_questions, 0) * 100 >= 40 THEN '40-60'
                            WHEN score::float / NULLIF(total_questions, 0) * 100 >= 20 THEN '20-40'
                            ELSE '0-20'
                        END AS bucket,
                        COUNT(*) AS count
                    FROM quiz_results
                    WHERE total_questions > 0
                    GROUP BY bucket
                    ORDER BY bucket
                """)
                distribution_rows = cursor.fetchall()
                score_distribution = {
                    row["bucket"]: row["count"] for row in distribution_rows
                }
                # Ensure all buckets exist
                for b in ["0-20", "20-40", "40-60", "60-80", "80-100"]:
                    score_distribution.setdefault(b, 0)

                # Popular topics (from metadata -> selected_folders)
                cursor.execute("""
                    SELECT
                        jsonb_array_elements_text(metadata->'selected_folders') AS folder,
                        COUNT(*) AS quiz_count
                    FROM quiz_results
                    WHERE metadata ? 'selected_folders'
                      AND jsonb_typeof(metadata->'selected_folders') = 'array'
                    GROUP BY folder
                    ORDER BY quiz_count DESC
                    LIMIT 10
                """)
                topic_rows = cursor.fetchall()
                popular_topics = [
                    {
                        "folder": str(row.get("folder") or "Unknown"),
                        "quiz_count": _coerce_int(row.get("quiz_count")),
                    }
                    for row in topic_rows
                ]

                # Recent activity (last 7 days, grouped by day)
                cursor.execute("""
                    SELECT
                        DATE(created_at) AS quiz_date,
                        COUNT(*) AS count,
                        COALESCE(AVG(score::float / NULLIF(total_questions, 0) * 100), 0) AS avg_score
                    FROM quiz_results
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY quiz_date
                """)
                activity_rows = cursor.fetchall()
                recent_activity = [
                    {
                        "date": row["quiz_date"].isoformat() if row["quiz_date"] else "",
                        "count": _coerce_int(row.get("count")),
                        "avg_score": round(_coerce_float(row.get("avg_score")), 1),
                    }
                    for row in activity_rows
                ]

                # Top performers
                cursor.execute("""
                    SELECT
                        username,
                        COUNT(*) AS quizzes_taken,
                        COALESCE(AVG(score::float / NULLIF(total_questions, 0) * 100), 0) AS avg_score
                    FROM quiz_results
                    WHERE total_questions > 0
                    GROUP BY username
                    ORDER BY avg_score DESC
                    LIMIT 5
                """)
                performer_rows = cursor.fetchall()
                top_performers = [
                    {
                        "username": str(row.get("username") or "Unknown"),
                        "quizzes_taken": _coerce_int(row.get("quizzes_taken")),
                        "avg_score": round(_coerce_float(row.get("avg_score")), 1),
                    }
                    for row in performer_rows
                ]

            return {
                "total_quizzes": _coerce_int(stats_row.get("total_quizzes") if stats_row else 0),
                "unique_users": _coerce_int(stats_row.get("unique_users") if stats_row else 0),
                "avg_percentage": round(_coerce_float(stats_row.get("avg_percentage") if stats_row else 0), 1),
                "highest_percentage": round(_coerce_float(stats_row.get("highest_percentage") if stats_row else 0), 1),
                "lowest_percentage": round(_coerce_float(stats_row.get("lowest_percentage") if stats_row else 0), 1),
                "total_questions_answered": _coerce_int(
                    stats_row.get("total_questions_answered") if stats_row else 0
                ),
                "score_distribution": score_distribution,
                "popular_topics": popular_topics,
                "recent_activity": recent_activity,
                "top_performers": top_performers,
            }
        except Exception as e:
            logger.error(f"Error getting quiz metrics: {e}")
            logger.warning(f"Admin service error: {e}")
            return {"error": "Failed to fetch quiz metrics", "total_quizzes": 0}

    # ── Dashboard Stats ──────────────────────────────────────────

    def _empty_admin_stats(self, error: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "total_users": 0,
            "total_queries": 0,
            "total_feedback": 0,
            "new_feedback": 0,
            "total_message_likes": 0,
            "total_message_dislikes": 0,
            "total_message_reports": 0,
            "total_chat_shares": 0,
            "active_announcements": 0,
            "admin_users": 0,
            "pending_appointments": 0,
            "storage_readiness": self.get_storage_readiness(),
        }
        if error:
            data["error"] = error
        return data

    def get_storage_readiness(self) -> Dict[str, Any]:
        raw_path = Path(config.USER_DATA_ROOT)
        path = raw_path.expanduser()
        try:
            resolved_path = path.resolve(strict=False)
        except OSError:
            resolved_path = path

        path_str = str(resolved_path)
        path_lower = path_str.lower()
        shared_storage = bool(config.USER_DATA_SHARED_STORAGE)
        path_exists = resolved_path.exists()
        try:
            is_mount = resolved_path.is_mount()
        except OSError:
            is_mount = False
        looks_persistent = any(
            marker in path_lower
            for marker in ("efs", "persistent", "mnt", "volume", "/data")
        )
        inferred_shared_storage = path_exists and (is_mount or looks_persistent)

        ready = config.ENVIRONMENT != "production" or shared_storage or inferred_shared_storage
        warning = None
        if config.ENVIRONMENT == "production" and not ready:
            warning = (
                "USER_DATA_ROOT is used for appointments and feedback, but "
                "no shared or mounted persistent storage was detected."
            )

        return {
            "ready": ready,
            "environment": config.ENVIRONMENT,
            "user_data_root": path_str,
            "path_exists": path_exists,
            "shared_storage_configured": shared_storage,
            "path_looks_persistent": looks_persistent,
            "path_is_mount": is_mount,
            "warning": warning,
        }

    def get_all_appointments(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        return [appt.to_dict() for appt in self.appointments.list_all(status=status, limit=limit)]

    def update_appointment_status(
        self, appointment_id: str, new_status: str
    ) -> Optional[Dict[str, Any]]:
        appointment = self.appointments.update_status(appointment_id, new_status)
        return appointment.to_dict() if appointment else None

    def get_admin_stats(self) -> Dict[str, Any]:
        try:
            users = self.list_users()
            feedback = self.get_all_feedback(limit=10000)
            announcements = self.list_announcements()
            appointments = self.get_all_appointments(limit=10000)
            message_feedback = self._summarize_message_feedback()
            share_actions = self._count_share_actions()

            # Count query logs from RAG evaluation logs
            total_queries = 0
            log_path = Path("logs") / "rag_evaluation.jsonl"
            if log_path.exists():
                try:
                    with log_path.open("r", encoding="utf-8") as f:
                        total_queries = sum(1 for line in f if line.strip())
                except OSError:
                    pass

            feedback_statuses = self._load_feedback_statuses()
            new_feedback = sum(
                1
                for fb in feedback
                if feedback_statuses.get(fb.get("id"), {}).get("status", "new") == "new"
            )

            return {
                "total_users": len(users),
                "total_queries": total_queries,
                "total_feedback": len(feedback),
                "new_feedback": new_feedback,
                "total_message_likes": message_feedback["thumbs_up"],
                "total_message_dislikes": message_feedback["thumbs_down"],
                "total_message_reports": message_feedback["report"],
                "total_chat_shares": share_actions,
                "active_announcements": sum(
                    1 for a in announcements if a.get("active", True)
                ),
                "admin_users": sum(1 for u in users if u.get("role") == "Admin"),
                "pending_appointments": sum(
                    1 for appt in appointments if appt.get("status") == "pending"
                ),
                "storage_readiness": self.get_storage_readiness(),
            }
        except Exception as e:
            logger.error("Error getting admin stats: %s", e)
            logger.warning(f"Admin service error: {e}")
            return self._empty_admin_stats("Failed to fetch admin stats")

    def _empty_agent_metrics(self, error: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "total_agent_interactions": 0,
            "unique_users": 0,
            "agent_distribution": {},
            "avg_response_time_ms": 0,
            "response_time_by_agent": {},
            "daily_usage": [],
            "top_query_types": [],
            "routing_accuracy": {
                "positive_after_route": 0,
                "negative_after_route": 0,
            },
        }
        if error:
            data["error"] = error
        return data

    def _empty_knowledge_graph_metrics(
        self, error: Optional[str] = None
    ) -> Dict[str, Any]:
        data = {
            "total_nodes": 0,
            "total_relationships": 0,
            "nodes_by_type": {},
            "relationships_by_type": {},
            "most_struggled_concepts": [],
            "most_studied_topics": [],
            "student_engagement": [],
            "feedback_sentiment_overview": {},
        }
        if error:
            data["error"] = error
        return data

    def _load_runtime_metric_records(self) -> List[Dict[str, Any]]:
        log_file = Path(config.EVALUATION_LOG_FILE)
        if not log_file.exists():
            return []

        records: List[Dict[str, Any]] = []
        try:
            with log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        records.append(record)
        except OSError as exc:
            logger.warning("Failed to read runtime metrics log: %s", exc)
        return records

    def _get_agent_metrics_from_runtime_logs(self) -> Dict[str, Any]:
        records = []
        for record in self._load_runtime_metric_records():
            metadata = record.get("metadata") or {}
            if metadata.get("mode") == "evaluation":
                continue
            if not metadata.get("agent"):
                continue
            records.append(record)

        if not records:
            return self._empty_agent_metrics()

        total = len(records)
        users = set()
        agent_counts: Dict[str, int] = {}
        agent_latencies: Dict[str, List[float]] = {}
        daily: Dict[str, Dict[str, Any]] = {}
        query_type_counts: Dict[str, int] = {}
        pos = 0
        neg = 0
        latency_values: List[float] = []

        for record in records:
            metadata = record.get("metadata") or {}
            agent = metadata.get("agent") or "unknown"
            user_id = metadata.get("user_id")
            query_type = metadata.get("query_type") or "unknown"
            sentiment = metadata.get("sentiment")
            ts = (record.get("timestamp") or "")[:10]

            total_seconds = (
                (record.get("end_to_end_metrics") or {}).get("total_time_seconds")
                or 0
            )
            latency_ms = float(total_seconds) * 1000 if total_seconds else 0.0

            if user_id:
                users.add(user_id)

            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            query_type_counts[query_type] = query_type_counts.get(query_type, 0) + 1

            if latency_ms > 0:
                latency_values.append(latency_ms)
                agent_latencies.setdefault(agent, []).append(latency_ms)

            if sentiment == "positive":
                pos += 1
            elif sentiment == "negative":
                neg += 1

            if ts:
                bucket = daily.setdefault(ts, {"users": set(), "count": 0})
                bucket["count"] += 1
                if user_id:
                    bucket["users"].add(user_id)

        feedback_total = pos + neg
        return {
            "total_agent_interactions": total,
            "unique_users": len(users),
            "agent_distribution": dict(
                sorted(agent_counts.items(), key=lambda item: item[1], reverse=True)
            ),
            "avg_response_time_ms": round(sum(latency_values) / len(latency_values), 0)
            if latency_values
            else 0,
            "response_time_by_agent": {
                agent: round(sum(values) / len(values), 0)
                for agent, values in agent_latencies.items()
                if values
            },
            "daily_usage": [
                {
                    "date": date,
                    "count": bucket["count"],
                    "unique_users": len(bucket["users"]),
                }
                for date, bucket in sorted(daily.items())
            ],
            "top_query_types": [
                {"type": query_type, "count": count}
                for query_type, count in sorted(
                    query_type_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10]
            ],
            "routing_accuracy": {
                "positive_after_route": round(pos / feedback_total * 100, 1)
                if feedback_total
                else 0,
                "negative_after_route": round(neg / feedback_total * 100, 1)
                if feedback_total
                else 0,
            },
            "source": "runtime_logs",
        }


    # ── Agent Metrics ──────────────────────────────────────────────

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Aggregate agent usage metrics from Neo4j AgentInteraction nodes."""
        try:
            from backend.agents.neo4j_client import get_neo4j_client

            client = get_neo4j_client()

            # Overall stats
            stats_rows = client.execute_read(
                "MATCH (s:Student)-[:HAD_AGENT_INTERACTION]->(ai:AgentInteraction) "
                "RETURN COUNT(ai) AS total, "
                "COUNT(DISTINCT s.username) AS unique_users, "
                "COALESCE(avg(ai.response_time_ms), 0) AS avg_rt"
            )
            row = stats_rows[0] if stats_rows else {}
            total = _coerce_int(row.get("total"))
            unique_users = _coerce_int(row.get("unique_users"))
            avg_rt = round(_coerce_float(row.get("avg_rt")), 0)

            # Agent distribution
            dist_rows = client.execute_read(
                "MATCH (ai:AgentInteraction) "
                "RETURN ai.agent AS agent, COUNT(*) AS cnt "
                "ORDER BY cnt DESC"
            )
            agent_dist = {
                str(r.get("agent") or "unknown"): _coerce_int(r.get("cnt"))
                for r in dist_rows
            }

            # Response time by agent
            rt_rows = client.execute_read(
                "MATCH (ai:AgentInteraction) "
                "WHERE ai.response_time_ms IS NOT NULL "
                "RETURN ai.agent AS agent, avg(ai.response_time_ms) AS avg_rt "
            )
            rt_by_agent = {
                str(r.get("agent") or "unknown"): round(_coerce_float(r.get("avg_rt")), 0)
                for r in rt_rows
            }

            # Daily usage (last 14 days)
            daily_rows = client.execute_read(
                "MATCH (s:Student)-[:HAD_AGENT_INTERACTION]->(ai:AgentInteraction) "
                "WHERE ai.timestamp >= datetime() - duration('P14D') "
                "WITH substring(ai.timestamp, 0, 10) AS d, ai, s "
                "RETURN d AS date, COUNT(ai) AS count, "
                "COUNT(DISTINCT s.username) AS unique_users "
                "ORDER BY d"
            )
            daily = [
                {
                    "date": r["date"],
                    "count": _coerce_int(r.get("count")),
                    "unique_users": _coerce_int(r.get("unique_users")),
                }
                for r in daily_rows
            ]

            # Top query types
            qt_rows = client.execute_read(
                "MATCH (ai:AgentInteraction) "
                "RETURN COALESCE(ai.query_type, 'unknown') AS type, COUNT(*) AS count "
                "ORDER BY count DESC LIMIT 10"
            )
            top_qt = [
                {
                    "type": str(r.get("type") or "unknown"),
                    "count": _coerce_int(r.get("count")),
                }
                for r in qt_rows
            ]

            # Routing accuracy (feedback-based)
            fb_rows = client.execute_read(
                "MATCH (ai:AgentInteraction) "
                "WHERE ai.sentiment IS NOT NULL "
                "RETURN "
                "SUM(CASE WHEN ai.sentiment = 'positive' THEN 1 ELSE 0 END) AS pos, "
                "SUM(CASE WHEN ai.sentiment = 'negative' THEN 1 ELSE 0 END) AS neg"
            )
            fb_row = fb_rows[0] if fb_rows else {}
            pos = _coerce_int(fb_row.get("pos"))
            neg = _coerce_int(fb_row.get("neg"))
            fb_total = pos + neg
            routing_acc = {
                "positive_after_route": round(pos / fb_total * 100, 1) if fb_total else 0,
                "negative_after_route": round(neg / fb_total * 100, 1) if fb_total else 0,
            }

            neo4j_metrics = {
                "total_agent_interactions": total,
                "unique_users": unique_users,
                "agent_distribution": agent_dist,
                "avg_response_time_ms": avg_rt,
                "response_time_by_agent": rt_by_agent,
                "daily_usage": daily,
                "top_query_types": top_qt,
                "routing_accuracy": routing_acc,
            }
            if total == 0:
                fallback = self._get_agent_metrics_from_runtime_logs()
                if fallback.get("total_agent_interactions", 0) > 0:
                    return fallback
            return neo4j_metrics
        except Exception as e:
            logger.error("Error getting agent metrics: %s", e)
            logger.warning(f"Admin service error: {e}")
            fallback = self._get_agent_metrics_from_runtime_logs()
            if fallback.get("total_agent_interactions", 0) > 0:
                return fallback
            return self._empty_agent_metrics("Failed to fetch agent metrics")

    # ── Knowledge Graph Metrics ───────────────────────────────────

    def get_knowledge_graph_metrics(self) -> Dict[str, Any]:
        """Query Neo4j for knowledge graph statistics."""
        try:
            from backend.agents.neo4j_client import get_neo4j_client

            client = get_neo4j_client()

            # Node counts by type
            nodes_by_type_rows = client.execute_read(
                "MATCH (n) RETURN labels(n)[0] AS type, COUNT(*) AS count"
            )
            nodes_by_type = {
                str(r.get("type") or "Unknown"): _coerce_int(r.get("count"))
                for r in nodes_by_type_rows
            }
            total_nodes = sum(nodes_by_type.values())

            # Relationship counts by type
            rels_by_type_rows = client.execute_read(
                "MATCH ()-[r]->() RETURN type(r) AS type, COUNT(*) AS count"
            )
            rels_by_type = {
                str(r.get("type") or "Unknown"): _coerce_int(r.get("count"))
                for r in rels_by_type_rows
            }
            total_rels = sum(rels_by_type.values())

            # Most struggled concepts
            struggled_rows = client.execute_read(
                "MATCH (s:Student)-[:STRUGGLES_WITH]->(c:Concept) "
                "RETURN c.name AS concept, COUNT(DISTINCT s) AS students "
                "ORDER BY students DESC LIMIT 10"
            )
            most_struggled = [
                {
                    "concept": str(r.get("concept") or "Unknown"),
                    "students": _coerce_int(r.get("students")),
                }
                for r in struggled_rows
            ]

            # Most studied topics
            studied_rows = client.execute_read(
                "MATCH (s:Student)-[r:STUDIED]->(t:Topic) "
                "RETURN t.name AS topic, SUM(r.study_count) AS study_count "
                "ORDER BY study_count DESC LIMIT 10"
            )
            most_studied = [
                {
                    "topic": str(r.get("topic") or "Unknown"),
                    "study_count": _coerce_int(r.get("study_count")),
                }
                for r in studied_rows
            ]

            # Student engagement
            engagement_rows = client.execute_read(
                "MATCH (s:Student) "
                "RETURN s.username AS username, "
                "COALESCE(s.total_queries, 0) AS queries, "
                "COALESCE(s.total_tutoring_sessions, 0) AS sessions, "
                "COALESCE(s.total_doubts, 0) AS doubts "
                "ORDER BY queries DESC LIMIT 20"
            )
            student_engagement = [
                {
                    "username": str(r.get("username") or "Unknown"),
                    "queries": _coerce_int(r.get("queries")),
                    "sessions": _coerce_int(r.get("sessions")),
                    "doubts": _coerce_int(r.get("doubts")),
                }
                for r in engagement_rows
            ]

            # Feedback sentiment overview
            feedback_rows = client.execute_read(
                "MATCH (f:Feedback) "
                "RETURN f.sentiment AS sentiment, COUNT(*) AS count"
            )
            feedback_sentiment = {
                str(r.get("sentiment") or "unknown"): _coerce_int(r.get("count"))
                for r in feedback_rows
            }

            return {
                "total_nodes": total_nodes,
                "total_relationships": total_rels,
                "nodes_by_type": nodes_by_type,
                "relationships_by_type": rels_by_type,
                "most_struggled_concepts": most_struggled,
                "most_studied_topics": most_studied,
                "student_engagement": student_engagement,
                "feedback_sentiment_overview": feedback_sentiment,
            }
        except Exception as e:
            logger.error("Error getting knowledge graph metrics: %s", e)
            logger.warning(f"Admin service error: {e}")
            return self._empty_knowledge_graph_metrics(
                "Failed to fetch knowledge graph metrics"
            )


_admin_service: Optional[AdminService] = None


def get_admin_service() -> AdminService:
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service
