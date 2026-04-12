"""SQLAlchemy models for the PostgreSQL schema managed by Alembic."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, desc, text
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
