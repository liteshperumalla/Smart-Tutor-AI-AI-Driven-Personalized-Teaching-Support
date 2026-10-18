"""Course tenancy, learning objectives, and evidence-based mastery.

The service deliberately keeps the first release transparent: quiz answers are
the only events that change mastery.  Self-reported confidence is useful for
recommendations, but never treated as proof of knowledge.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
import uuid

from fastapi import HTTPException, status

from backend.config import config
from backend.database import JSONDatabase


SEED_COURSE_ID = "info-5731"
_DIFFICULTY_WEIGHT = {"easy": 0.8, "medium": 1.0, "hard": 1.2}

_SEED_COURSE = {
    "id": SEED_COURSE_ID,
    "code": "INFO 5731",
    "title": "Computational Methods for Information Systems",
    "description": "The original Smart Tutor AI course workspace.",
    "owner_username": None,
    "open_enrollment": True,
    # Quiz folders are S3-relative (for example ``module_8``); retrieval
    # sources may also retain the ``modules/`` prefix.
    "resource_prefixes": ["modules/module_", "module_"],
    "modules": [
        {
            "id": "information-extraction",
            "title": "Information Extraction",
            "resource_prefixes": ["modules/module_8", "module_8"],
            "objectives": [
                {"id": "ie-foundations", "title": "Explain information extraction concepts", "module_id": "information-extraction"},
                {"id": "ie-keyphrases", "title": "Compare keyphrase extraction approaches", "module_id": "information-extraction"},
                {"id": "ie-knowledge-graphs", "title": "Apply information extraction to knowledge graphs", "module_id": "information-extraction"},
            ],
        }
    ],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


class LearningService:
    def __init__(self, data_path: str | Path | None = None) -> None:
        path = Path(data_path or Path(config.USER_DATA_ROOT) / "learning_state.json")
        self.db = JSONDatabase(str(path))
        self._ensure_seed_data()

    def _ensure_seed_data(self) -> None:
        with self.db.transaction() as data:
            data.setdefault("courses", {})
            data.setdefault("memberships", {})
            data.setdefault("mastery", {})
            data.setdefault("evidence", {})
            data.setdefault("confidence", {})
            data.setdefault("quiz_items", {})
            if SEED_COURSE_ID not in data["courses"]:
                data["courses"][SEED_COURSE_ID] = deepcopy(_SEED_COURSE)

    def _course(self, data: dict[str, Any], course_id: str) -> dict[str, Any]:
        course = data["courses"].get(course_id)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        return course

    @staticmethod
    def _is_admin(user: dict[str, Any]) -> bool:
        metadata = user.get("metadata") or {}
        return user.get("role") == "Admin" or bool(metadata.get("is_admin"))

    def _membership(self, data: dict[str, Any], username: str, course_id: str) -> dict[str, Any] | None:
        return data["memberships"].get(f"{username}:{course_id}")

    def require_access(self, username: str, user: dict[str, Any], course_id: str, roles: Iterable[str] | None = None) -> dict[str, Any]:
        with self.db.transaction() as data:
            course = self._course(data, course_id)
            membership = self._membership(data, username, course_id)
            if not membership and not self._is_admin(user):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this course")
            if roles and not self._is_admin(user):
                if not membership or membership.get("role") not in set(roles):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Instructor access required")
            return deepcopy(course)

    def list_courses(self, username: str, user: dict[str, Any]) -> list[dict[str, Any]]:
        with self.db.transaction() as data:
            courses = []
            for course in data["courses"].values():
                membership = self._membership(data, username, course["id"])
                if membership or self._is_admin(user):
                    result = deepcopy(course)
                    result["membership_role"] = membership.get("role", "admin") if membership else "admin"
                    courses.append(result)
            return sorted(courses, key=lambda item: item["code"])

    def list_enrollable_courses(self, username: str, user: dict[str, Any]) -> list[dict[str, Any]]:
        """List public course metadata without granting access to its content."""
        with self.db.transaction() as data:
            catalog = []
            for course in data["courses"].values():
                if course.get("open_enrollment") or self._is_admin(user):
                    catalog.append({
                        "id": course["id"],
                        "code": course["code"],
                        "title": course["title"],
                        "description": course.get("description", ""),
                        "enrolled": bool(self._membership(data, username, course["id"])),
                    })
            return sorted(catalog, key=lambda item: item["code"])

    def create_course(self, username: str, payload: dict[str, Any]) -> dict[str, Any]:
        course_id = payload.get("id") or payload.get("code", "").lower().replace(" ", "-")
        if not course_id:
            raise HTTPException(status_code=422, detail="Course id or code is required")
        with self.db.transaction() as data:
            if course_id in data["courses"]:
                raise HTTPException(status_code=409, detail="Course already exists")
            course = {
                "id": course_id,
                "code": payload["code"],
                "title": payload["title"],
                "description": payload.get("description", ""),
                "owner_username": username,
                "open_enrollment": bool(payload.get("open_enrollment", False)),
                "resource_prefixes": payload.get("resource_prefixes", []),
                "modules": payload.get("modules", []),
            }
            data["courses"][course_id] = course
            data["memberships"][f"{username}:{course_id}"] = {"username": username, "course_id": course_id, "role": "instructor", "active": True, "enrolled_at": _iso()}
            return deepcopy(course)

    def enroll(self, username: str, user: dict[str, Any], course_id: str) -> dict[str, Any]:
        with self.db.transaction() as data:
            course = self._course(data, course_id)
            if not course.get("open_enrollment") and not self._is_admin(user):
                raise HTTPException(status_code=403, detail="This course requires instructor enrollment")
            membership = {"username": username, "course_id": course_id, "role": "student", "active": True, "enrolled_at": _iso()}
            data["memberships"][f"{username}:{course_id}"] = membership
            return deepcopy(membership)

    def memberships(self, username: str, user: dict[str, Any], course_id: str) -> list[dict[str, Any]]:
        self.require_access(username, user, course_id, roles=("instructor",))
        with self.db.transaction() as data:
            return sorted(
                [deepcopy(item) for item in data["memberships"].values() if item["course_id"] == course_id],
                key=lambda item: (item["role"], item["username"]),
            )

    def set_membership(self, actor_username: str, actor: dict[str, Any], course_id: str, username: str, role: str) -> dict[str, Any]:
        self.require_access(actor_username, actor, course_id, roles=("instructor",))
        if role not in {"student", "instructor"}:
            raise HTTPException(status_code=422, detail="Membership role must be student or instructor")
        with self.db.transaction() as data:
            self._course(data, course_id)
            membership = {
                "username": username,
                "course_id": course_id,
                "role": role,
                "active": True,
                "enrolled_at": data["memberships"].get(f"{username}:{course_id}", {}).get("enrolled_at", _iso()),
            }
            data["memberships"][f"{username}:{course_id}"] = membership
            return deepcopy(membership)

    def remove_membership(self, actor_username: str, actor: dict[str, Any], course_id: str, username: str) -> None:
        self.require_access(actor_username, actor, course_id, roles=("instructor",))
        with self.db.transaction() as data:
            membership = data["memberships"].get(f"{username}:{course_id}")
            if not membership:
                raise HTTPException(status_code=404, detail="Course membership not found")
            if membership.get("role") == "instructor" and membership.get("username") == actor_username and not self._is_admin(actor):
                raise HTTPException(status_code=400, detail="Assign another instructor before removing yourself")
            del data["memberships"][f"{username}:{course_id}"]

    def objectives(self, username: str, user: dict[str, Any], course_id: str) -> list[dict[str, Any]]:
        course = self.require_access(username, user, course_id)
        return [deepcopy(objective) for module in course.get("modules", []) for objective in module.get("objectives", [])]

    def course_prefixes(self, username: str, user: dict[str, Any], course_id: str, module_id: str | None = None) -> list[str]:
        course = self.require_access(username, user, course_id)
        if module_id:
            module = next((item for item in course.get("modules", []) if item.get("id") == module_id), None)
            if not module:
                raise HTTPException(status_code=404, detail="Module not found in active course")
            return list(module.get("resource_prefixes") or course.get("resource_prefixes") or [])
        return list(course.get("resource_prefixes") or [])

    def validate_objectives(self, username: str, user: dict[str, Any], course_id: str, objective_ids: list[str] | None) -> list[str]:
        valid = {objective["id"] for objective in self.objectives(username, user, course_id)}
        requested = objective_ids or []
        unknown = set(requested) - valid
        if unknown:
            raise HTTPException(status_code=422, detail="Objectives must belong to the active course")
        return requested

    def record_assessment(self, username: str, course_id: str, responses: list[dict[str, Any]], difficulty: str = "medium") -> list[dict[str, Any]]:
        """Record item-level quiz evidence and return the updated objective snapshots."""
        weight = _DIFFICULTY_WEIGHT.get(difficulty, 1.0)
        with self.db.transaction() as data:
            snapshots = []
            for response in responses:
                objective_id = response.get("objective_id")
                if not objective_id:
                    continue
                key = f"{username}:{course_id}:{objective_id}"
                existing = data["mastery"].get(key, {"username": username, "course_id": course_id, "objective_id": objective_id, "score": 0.5, "attempts": 0, "correct": 0})
                is_correct = bool(response.get("is_correct"))
                delta = (0.12 if is_correct else -0.18) * weight
                existing["score"] = round(max(0.0, min(1.0, float(existing["score"]) + delta)), 3)
                existing["attempts"] += 1
                existing["correct"] += int(is_correct)
                existing["last_assessed_at"] = _iso()
                existing["next_review_at"] = _iso(_now() + timedelta(days=14 if existing["score"] >= 0.8 else 3 if existing["score"] >= 0.5 else 1))
                data["mastery"][key] = existing
                data["evidence"].setdefault(key, []).append({"id": uuid.uuid4().hex, "objective_id": objective_id, "is_correct": is_correct, "difficulty": difficulty, "source": "quiz", "created_at": _iso()})
                snapshots.append(deepcopy(existing))
            return snapshots

    def register_quiz_items(self, course_id: str, quiz_id: str, questions: list[dict[str, Any]]) -> None:
        """Persist generated item/objective links for instructor coverage reporting.

        This is content inventory, not learner evidence: it can never change
        mastery and is intentionally separate from ``record_assessment``.
        """
        with self.db.transaction() as data:
            for question in questions:
                objective_id = question.get("objective_id")
                question_id = question.get("id")
                if not objective_id or not question_id:
                    continue
                data["quiz_items"][f"{course_id}:{question_id}"] = {
                    "id": question_id,
                    "quiz_id": quiz_id,
                    "course_id": course_id,
                    "objective_id": objective_id,
                    "created_at": _iso(),
                }

    def objective_coverage(self, username: str, user: dict[str, Any], course_id: str) -> dict[str, Any]:
        self.require_access(username, user, course_id, roles=("instructor",))
        objectives = self.objectives(username, user, course_id)
        with self.db.transaction() as data:
            items = [item for item in data["quiz_items"].values() if item.get("course_id") == course_id]
            evidence = [entry for key, entries in data["evidence"].items() if key.split(":", 2)[1:2] == [course_id] for entry in entries]
        rows = []
        for objective in objectives:
            item_count = sum(1 for item in items if item.get("objective_id") == objective["id"])
            assessed_count = sum(1 for entry in evidence if entry.get("objective_id") == objective["id"])
            # Older assessment records predate explicit objective fields.  The
            # mastery total remains available in the course summary; coverage
            # deliberately only counts records with a known objective.
            rows.append({
                "objective_id": objective["id"],
                "title": objective["title"],
                "module_id": objective["module_id"],
                "quiz_item_count": item_count,
                "assessed_item_count": assessed_count,
                "covered": item_count > 0,
            })
        covered = sum(1 for row in rows if row["covered"])
        return {"course_id": course_id, "total_objectives": len(rows), "covered_objectives": covered, "coverage_pct": round(covered / len(rows) * 100, 1) if rows else 0.0, "objectives": rows}

    def content_ingestion_status(self, username: str, user: dict[str, Any], course_id: str) -> dict[str, Any]:
        """Return indexing health for documents explicitly assigned to a course."""
        self.require_access(username, user, course_id, roles=("instructor",))
        from backend.services.resource_service import get_resource_service
        resource_service = get_resource_service()
        if course_id == SEED_COURSE_ID:
            resource_service.assign_unscoped_resources_to_course(course_id)
        try:
            from backend.services.indexing_service import get_indexing_service
            indexing = get_indexing_service()
        except Exception:
            indexing = None
        resources = [r for r in resource_service.list_resources(include_inactive=True) if r.get("course_id") == course_id]
        documents = []
        for resource in resources:
            if resource.get("type") != "file":
                continue
            progress = indexing.get_status(resource["id"]) if indexing else None
            ext = Path(resource.get("file_name") or "").suffix.lower()
            indexable = ext in {".pdf", ".pptx", ".docx", ".txt", ".md", ".ipynb"}
            record = progress or {"status": "not_started", "progress_pct": 0, "chunks_created": 0, "total_chunks": None, "error": None}
            documents.append({"resource_id": resource["id"], "title": resource.get("title"), "file_name": resource.get("file_name"), "active": resource.get("active", True), "indexable": indexable, **record})
        counts: dict[str, int] = {}
        for document in documents:
            counts[document["status"]] = counts.get(document["status"], 0) + 1
        return {"course_id": course_id, "total_documents": len(documents), "indexable_documents": sum(1 for d in documents if d["indexable"]), "status_counts": counts, "documents": documents}

    def set_confidence(self, username: str, user: dict[str, Any], course_id: str, objective_id: str, confidence: int) -> dict[str, Any]:
        self.validate_objectives(username, user, course_id, [objective_id])
        if confidence not in range(1, 6):
            raise HTTPException(status_code=422, detail="Confidence must be from 1 to 5")
        with self.db.transaction() as data:
            record = {"username": username, "course_id": course_id, "objective_id": objective_id, "confidence": confidence, "updated_at": _iso()}
            data["confidence"][f"{username}:{course_id}:{objective_id}"] = record
            return deepcopy(record)

    def _snapshots(self, data: dict[str, Any], username: str, course_id: str, objectives: list[dict[str, Any]]) -> list[dict[str, Any]]:
        snapshots = []
        for objective in objectives:
            key = f"{username}:{course_id}:{objective['id']}"
            snapshot = deepcopy(data["mastery"].get(key, {"username": username, "course_id": course_id, "objective_id": objective["id"], "score": 0.0, "attempts": 0, "correct": 0, "next_review_at": None}))
            snapshot["title"] = objective["title"]
            snapshot["module_id"] = objective["module_id"]
            snapshot["self_confidence"] = data["confidence"].get(key, {}).get("confidence")
            snapshots.append(snapshot)
        return snapshots

    def recommendation(self, username: str, user: dict[str, Any], course_id: str) -> dict[str, Any]:
        objectives = self.objectives(username, user, course_id)
        with self.db.transaction() as data:
            snapshots = self._snapshots(data, username, course_id, objectives)
            now = _now()
            due = [item for item in snapshots if item.get("next_review_at") and datetime.fromisoformat(item["next_review_at"]) <= now]
            target = min(due or snapshots, key=lambda item: (item.get("score", 0.0), item.get("attempts", 0))) if snapshots else None
            if not target:
                return {"course_id": course_id, "recommendation": None}
            reason = "Start a diagnostic practice set" if target["attempts"] == 0 else ("Review this objective before it is due" if target in due else "Strengthen your lowest-mastery objective")
            return {"course_id": course_id, "recommendation": {"objective_id": target["objective_id"], "title": target["title"], "module_id": target["module_id"], "mastery": target["score"], "reason": reason, "difficulty": "easy" if target["score"] < 0.4 else "medium"}}

    def dashboard(self, username: str, user: dict[str, Any], course_id: str | None = None) -> dict[str, Any]:
        courses = self.list_courses(username, user)
        if not courses:
            return {"course": None, "mastery": [], "recommendation": None, "weekly_goal": {"target": 3, "completed": 0}}
        active_id = course_id or courses[0]["id"]
        self.require_access(username, user, active_id)
        objectives = self.objectives(username, user, active_id)
        with self.db.transaction() as data:
            mastery = self._snapshots(data, username, active_id, objectives)
            week_ago = _now() - timedelta(days=7)
            evidence = [entry for key, entries in data["evidence"].items() if key.startswith(f"{username}:{active_id}:") for entry in entries if datetime.fromisoformat(entry["created_at"]) >= week_ago]
        course = next(course for course in courses if course["id"] == active_id)
        recommendation = self.recommendation(username, user, active_id).get("recommendation")
        return {"course": {"id": course["id"], "code": course["code"], "title": course["title"]}, "mastery": mastery, "recommendation": recommendation, "weekly_goal": {"target": 3, "completed": len(evidence)}, "recent_activity": sorted(evidence, key=lambda item: item["created_at"], reverse=True)[:5]}

    def instructor_summary(self, username: str, user: dict[str, Any], course_id: str) -> dict[str, Any]:
        self.require_access(username, user, course_id, roles=("instructor",))
        objectives = self.objectives(username, user, course_id)
        with self.db.transaction() as data:
            memberships = [item for item in data["memberships"].values() if item["course_id"] == course_id and item["role"] == "student"]
            records = [item for key, item in data["mastery"].items() if key.split(":")[1] == course_id]
        by_objective = []
        for objective in objectives:
            scores = [record["score"] for record in records if record["objective_id"] == objective["id"]]
            by_objective.append({"objective_id": objective["id"], "title": objective["title"], "student_count": len(scores), "average_mastery": round(sum(scores) / len(scores), 3) if scores else None})
        return {"course_id": course_id, "enrolled_students": len(memberships), "objectives": by_objective}


_learning_service: LearningService | None = None


def get_learning_service() -> LearningService:
    global _learning_service
    if _learning_service is None:
        _learning_service = LearningService()
    return _learning_service
