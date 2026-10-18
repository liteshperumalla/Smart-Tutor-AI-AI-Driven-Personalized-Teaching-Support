"""SQLAlchemy models for the PostgreSQL schema managed by Alembic."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, Index, Integer, String, UniqueConstraint, desc, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base metadata container for Alembic."""


class UserRecord(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(), server_default=text("CURRENT_TIMESTAMP")
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime())
    login_attempts: Mapped[int | None] = mapped_column(
        Integer(), server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime())
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    __table_args__ = (Index("idx_users_email", "email"),)


class QuizResultRecord(Base):
    __tablename__ = "quiz_results"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False
    )
    quiz_id: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer())
    total_questions: Mapped[int | None] = mapped_column(Integer())
    answers: Mapped[list | dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(), server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    __table_args__ = (
        Index("idx_quiz_results_username", "username"),
        Index("idx_quiz_results_quiz_id", "quiz_id"),
        Index("idx_quiz_results_created_at", desc("created_at")),
    )


class CourseRecord(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_username: Mapped[str | None] = mapped_column(String(255), ForeignKey("users.username", ondelete="SET NULL"))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"))


class CourseMembershipRecord(Base):
    __tablename__ = "course_memberships"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'student'"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("course_id", "username", name="uq_course_membership"), Index("idx_course_memberships_username", "username"))


class LearningObjectiveRecord(Base):
    __tablename__ = "learning_objectives"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    __table_args__ = (Index("idx_learning_objectives_course", "course_id"),)


class MasteryRecord(Base):
    __tablename__ = "student_mastery"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    objective_id: Mapped[str] = mapped_column(String(128), ForeignKey("learning_objectives.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Float(), nullable=False, server_default=text("0"))
    attempts: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("username", "course_id", "objective_id", name="uq_student_mastery"), Index("idx_student_mastery_course", "course_id"))
