from __future__ import annotations

from fastapi import HTTPException
import pytest

from backend.services.learning_service import LearningService, SEED_COURSE_ID


@pytest.fixture
def service(tmp_path):
    return LearningService(tmp_path / "learning.json")


@pytest.fixture
def student():
    return {"username": "student@example.com", "role": "User", "metadata": {}}


def test_seed_course_requires_explicit_enrollment(service, student):
    catalog = service.list_enrollable_courses(student["username"], student)
    assert [course["id"] for course in catalog] == [SEED_COURSE_ID]
    assert catalog[0]["enrolled"] is False

    service.enroll(student["username"], student, SEED_COURSE_ID)
    courses = service.list_courses(student["username"], student)
    assert [course["id"] for course in courses] == [SEED_COURSE_ID]
    assert courses[0]["membership_role"] == "student"


def test_only_assessment_evidence_changes_mastery(service, student):
    service.enroll(student["username"], student, SEED_COURSE_ID)
    before = service.dashboard(student["username"], student, SEED_COURSE_ID)["mastery"][0]
    service.set_confidence(student["username"], student, SEED_COURSE_ID, before["objective_id"], 5)
    after_confidence = service.dashboard(student["username"], student, SEED_COURSE_ID)["mastery"][0]
    assert after_confidence["score"] == before["score"]

    service.record_assessment(student["username"], SEED_COURSE_ID, [{"objective_id": before["objective_id"], "is_correct": True}], "medium")
    after_assessment = service.dashboard(student["username"], student, SEED_COURSE_ID)["mastery"][0]
    assert after_assessment["score"] > before["score"]
    assert after_assessment["attempts"] == 1


def test_course_access_is_an_isolation_boundary(service, student):
    service.create_course("instructor", {"id": "private-course", "code": "PRIVATE 101", "title": "Private course"})
    with pytest.raises(HTTPException) as error:
        service.require_access(student["username"], student, "private-course")
    assert error.value.status_code == 403


def test_objective_coverage_tracks_generated_items_not_mastery(service):
    instructor = {"username": "instructor", "role": "Admin", "metadata": {}}
    objective_id = "ie-foundations"
    service.register_quiz_items(
        SEED_COURSE_ID,
        "quiz-1",
        [{"id": "item-1", "objective_id": objective_id}],
    )
    coverage = service.objective_coverage("instructor", instructor, SEED_COURSE_ID)
    foundation = next(item for item in coverage["objectives"] if item["objective_id"] == objective_id)
    assert foundation["covered"] is True
    assert foundation["quiz_item_count"] == 1


def test_instructor_can_manage_only_their_course_memberships(service):
    admin = {"username": "admin", "role": "Admin", "metadata": {}}
    course = service.create_course("admin", {"id": "new-course", "code": "NEW 101", "title": "New course"})
    service.set_membership("admin", admin, course["id"], "teacher", "instructor")
    teacher = {"username": "teacher", "role": "User", "metadata": {}}
    membership = service.set_membership("teacher", teacher, course["id"], "learner", "student")
    assert membership["role"] == "student"
    assert {item["username"] for item in service.memberships("teacher", teacher, course["id"])} == {"admin", "teacher", "learner"}

    service.remove_membership("teacher", teacher, course["id"], "learner")
    assert {item["username"] for item in service.memberships("teacher", teacher, course["id"])} == {"admin", "teacher"}
