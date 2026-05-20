from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from backend.config import config
from backend.database import UserDatabase
from backend.services.models import ChatMessage, ChatSession, QuizResult
from .base import BaseStorageBackend


def _parse_utc_or_now(value: Optional[str]) -> datetime:
    """Parse an ISO timestamp coercing naive values to aware UTC.

    Legacy persisted sessions may have naive ISO strings; sorting a mix of
    naive and aware datetimes raises TypeError. Returns `now` if the value
    is missing or malformed."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class FileSystemStorageBackend(BaseStorageBackend):
    """Storage backend that mirrors the current JSON/FS layout."""

    def __init__(self, user_db: Optional[UserDatabase] = None) -> None:
        self.user_db = user_db or UserDatabase()
        self.root = Path(config.USER_DATA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self.legacy_chat_root = Path(config.PREV_CHAT_DIR)
        self.legacy_quiz_root = Path(config.QUIZ_RESULTS_DIR)

    # -- User operations -------------------------------------------------
    def get_user(self, username: str) -> Optional[dict]:
        return self.user_db.get_user_safe(username)

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        return self.user_db.create_user(username, password_hash, **extras)

    def update_user(self, username: str, updates: dict) -> dict:
        return self.user_db.update_user(username, updates)

    # -- Chat helpers ----------------------------------------------------
    def _sanitize(self, value: str) -> str:
        return "".join(c if c.isalnum() or c in "-_." else "_" for c in value)

    def _sanitize_session_id(self, session_id: str) -> str:
        """Strip any path separators or control chars from session ids before
        they touch disk. Defense-in-depth against path traversal: a crafted
        session_id like `../../etc/passwd` would otherwise escape the chat dir.
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        cleaned = self._sanitize(session_id).strip(".")
        if not cleaned:
            raise ValueError(f"session_id is invalid: {session_id!r}")
        return cleaned

    def _user_dir(self, username: str) -> Path:
        base = self.root / self._sanitize(username)
        needs_migration = False
        if not base.exists():
            needs_migration = True
        else:
            try:
                next(base.iterdir())
            except StopIteration:
                needs_migration = True
            except FileNotFoundError:
                needs_migration = True

        if needs_migration and "@" in username:
            legacy_name = username.split("@", 1)[0]
            legacy_base = self.root / self._sanitize(legacy_name)
            if legacy_base.exists():
                base.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(legacy_base, base, dirs_exist_ok=True)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _chat_dir(self, username: str) -> Path:
        chat_dir = self._user_dir(username) / "chats"
        chat_dir.mkdir(parents=True, exist_ok=True)
        return chat_dir

    def _quiz_dir(self, username: str) -> Path:
        base = self._user_dir(username)
        legacy_dir = base / "quizzes"
        quiz_dir = base / "quiz"
        if legacy_dir.exists() and not quiz_dir.exists():
            shutil.move(str(legacy_dir), str(quiz_dir))
        quiz_dir.mkdir(parents=True, exist_ok=True)
        return quiz_dir

    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        self._migrate_legacy_chats(username)
        sessions: List[ChatSession] = []
        chat_dir = self._chat_dir(username)
        for path in chat_dir.glob("*.json"):
            if path.name == "index.json":
                continue
            session = self.load_chat_session(username, path.stem)
            if session:
                sessions.append(session)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        path = self._chat_dir(username) / f"{self._sanitize_session_id(session_id)}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        messages_data = data if isinstance(data, list) else data.get("messages", [])
        messages = [ChatMessage.from_dict(msg) for msg in messages_data]
        if isinstance(data, dict):
            title = data.get("title") or f"Session {session_id[:8]}"
            created = data.get("created_at")
            updated = data.get("updated_at")
        else:
            title = f"Session {session_id[:8]}"
            created = None
            updated = None
        return ChatSession(
            id=session_id,
            title=title,
            messages=messages,
            # Legacy JSON rows may have naive ISO strings; normalise to aware
            # UTC so downstream sorting of `updated_at` doesn't TypeError on
            # mixed naive/aware values.
            created_at=_parse_utc_or_now(created),
            updated_at=_parse_utc_or_now(updated),
        )

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        path = self._chat_dir(username) / f"{session.id}.json"
        payload = session.to_dict()
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def delete_chat_session(self, username: str, session_id: str) -> bool:
        path = self._chat_dir(username) / f"{self._sanitize_session_id(session_id)}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # -- Quiz helpers ----------------------------------------------------
    def save_quiz_result(self, result: QuizResult) -> None:
        directory = self._quiz_dir(result.user_id)
        path = directory / f"{result.id or uuid.uuid4().hex}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def list_quiz_results(self, username: str) -> List[QuizResult]:
        self._migrate_legacy_quizzes(username)
        directory = self._quiz_dir(username)
        results: List[QuizResult] = []
        for path in directory.glob("*.json"):
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            created_at = data.get("created_at") or data.get("timestamp") or datetime.now(timezone.utc).isoformat()
            metadata = data.get("metadata") or {
                "selected_folders": data.get("selected_folders", []),
                "questions_data": data.get("questions_data", []),
            }
            results.append(
                QuizResult(
                    id=data.get("id", path.stem),
                    user_id=username,
                    score=data.get("score", 0),
                    total_questions=data.get("total_questions", 0),
                    percentage=data.get("percentage", 0.0),
                    created_at=datetime.fromisoformat(created_at),
                    metadata=metadata,
                )
            )
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results

    # -- Legacy migration helpers ---------------------------------------
    def _legacy_marker(self, username: str, suffix: str) -> Path:
        return self._user_dir(username) / f".legacy_{suffix}_migrated"

    def _migrate_legacy_chats(self, username: str) -> None:
        if not self.legacy_chat_root.exists():
            return
        marker = self._legacy_marker(username, "chats")
        if marker.exists():
            return
        migrated = 0
        for legacy_file in sorted(self.legacy_chat_root.glob("*.json")):
            try:
                with legacy_file.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            session_id = self._sanitize(legacy_file.stem) or uuid.uuid4().hex
            target = self._chat_dir(username) / f"{session_id}.json"
            if target.exists():
                continue
            messages: List[ChatMessage] = []
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                data = dict(entry)
                timestamp = data.get("timestamp")
                if isinstance(timestamp, str) and "T" not in timestamp:
                    data["timestamp"] = timestamp.replace(" ", "T")
                try:
                    messages.append(ChatMessage.from_dict(data))
                except Exception:
                    continue
            if not messages:
                continue
            title = legacy_file.stem.replace("_", " ").strip() or f"Session {session_id[:6]}"
            created_at = messages[0].timestamp
            updated_at = messages[-1].timestamp
            session = ChatSession(
                id=session_id,
                title=title,
                messages=messages,
                created_at=created_at,
                updated_at=updated_at,
            )
            self.save_chat_session(username, session)
            migrated += 1
        marker.write_text(json.dumps({"migrated": migrated}), encoding="utf-8")

    def _migrate_legacy_quizzes(self, username: str) -> None:
        if not self.legacy_quiz_root.exists():
            return
        marker = self._legacy_marker(username, "quizzes")
        if marker.exists():
            return
        migrated = 0
        for legacy_file in sorted(self.legacy_quiz_root.glob("*.json")):
            target = self._quiz_dir(username) / f"{legacy_file.stem}.json"
            if target.exists():
                continue
            try:
                with legacy_file.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            score = int(payload.get("score") or payload.get("correct", 0) or 0)
            total_questions = int(
                payload.get("total_questions")
                or payload.get("total")
                or len(payload.get("questions", []))
                or 0
            )
            percentage = payload.get("percentage")
            if isinstance(percentage, (int, float)):
                pct_value = float(percentage)
            else:
                pct_value = (score / total_questions * 100) if total_questions else 0.0
            created_at = datetime.fromtimestamp(legacy_file.stat().st_mtime)
            metadata = {
                "source": "legacy_quiz_results",
                "questions": payload.get("questions", []),
            }
            result = QuizResult(
                id=legacy_file.stem,
                user_id=username,
                score=score,
                total_questions=total_questions,
                percentage=round(pct_value, 2),
                created_at=created_at,
                metadata=metadata,
            )
            self.save_quiz_result(result)
            migrated += 1
        marker.write_text(json.dumps({"migrated": migrated}), encoding="utf-8")
