"""Unit tests for SQLAlchemy models, relationships, and eager loading (Pattern 27)."""

import pytest
from sqlalchemy import inspect
from backend.db.models import (
    Base,
    UserRecord,
    QuizResultRecord,
    CourseRecord,
    CourseMembershipRecord,
    LearningObjectiveRecord,
    MasteryRecord,
)


def test_models_table_names():
    """Verify table name declarations across entities."""
    assert UserRecord.__tablename__ == "users"
    assert QuizResultRecord.__tablename__ == "quiz_results"
    assert CourseRecord.__tablename__ == "courses"
    assert CourseMembershipRecord.__tablename__ == "course_memberships"
    assert LearningObjectiveRecord.__tablename__ == "learning_objectives"
    assert MasteryRecord.__tablename__ == "student_mastery"


def test_user_record_eager_relationships_and_version():
    """Verify UserRecord relationships are configured with lazy='selectin' to prevent N+1 queries."""
    mapper = inspect(UserRecord)
    
    # Check version column for optimistic locking
    assert "version" in mapper.columns
    assert mapper.columns["version"].type.python_type == int

    # Check relationships
    relationships = mapper.relationships
    assert "quiz_results" in relationships
    assert relationships["quiz_results"].lazy == "selectin"
    assert relationships["quiz_results"].back_populates == "user"

    assert "course_memberships" in relationships
    assert relationships["course_memberships"].lazy == "selectin"
    assert relationships["course_memberships"].back_populates == "user"


def test_course_record_eager_relationships():
    """Verify CourseRecord relationships avoid N+1 queries via selectin loading."""
    mapper = inspect(CourseRecord)
    relationships = mapper.relationships

    assert "memberships" in relationships
    assert relationships["memberships"].lazy == "selectin"
    assert relationships["memberships"].back_populates == "course"

    assert "learning_objectives" in relationships
    assert relationships["learning_objectives"].lazy == "selectin"
    assert relationships["learning_objectives"].back_populates == "course"


def test_course_membership_and_mastery_relationships():
    """Verify CourseMembershipRecord and MasteryRecord relationships."""
    mem_mapper = inspect(CourseMembershipRecord)
    assert mem_mapper.relationships["course"].lazy == "selectin"
    assert mem_mapper.relationships["user"].lazy == "selectin"

    mastery_mapper = inspect(MasteryRecord)
    assert "version" in mastery_mapper.columns
    assert mastery_mapper.relationships["objective"].lazy == "selectin"
    assert mastery_mapper.relationships["user"].lazy == "selectin"
