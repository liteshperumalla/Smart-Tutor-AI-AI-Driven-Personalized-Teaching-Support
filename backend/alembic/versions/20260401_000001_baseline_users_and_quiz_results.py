"""Baseline PostgreSQL schema for users and quiz results."""

from typing import Iterable

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_000001"
down_revision = None
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def _add_missing_columns(
    table_name: str, existing_columns: set[str], columns: Iterable[sa.Column]
) -> None:
    for column in columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "users",
            sa.Column("username", sa.String(length=255), primary_key=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("last_login", sa.DateTime(), nullable=True),
            sa.Column(
                "login_attempts",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=True,
            ),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.create_index("idx_users_email", "users", ["email"], unique=False)
        op.create_table(
            "quiz_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("quiz_id", sa.String(length=255), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("total_questions", sa.Integer(), nullable=True),
            sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.ForeignKeyConstraint(
                ["username"],
                ["users.username"],
                name="fk_quiz_results_username_users",
                ondelete="CASCADE",
            ),
        )
        op.create_index("idx_quiz_results_username", "quiz_results", ["username"], unique=False)
        op.create_index("idx_quiz_results_quiz_id", "quiz_results", ["quiz_id"], unique=False)
        op.create_index("idx_quiz_results_created_at", "quiz_results", ["created_at"], unique=False)
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("username", sa.String(length=255), primary_key=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("last_login", sa.DateTime(), nullable=True),
            sa.Column(
                "login_attempts",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=True,
            ),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    else:
        existing = _column_names(inspector, "users")
        _add_missing_columns(
            "users",
            existing,
            (
                sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
                sa.Column("email", sa.String(length=255), nullable=True),
                sa.Column("full_name", sa.String(length=255), nullable=True),
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    nullable=True,
                ),
                sa.Column("last_login", sa.DateTime(), nullable=True),
                sa.Column(
                    "login_attempts",
                    sa.Integer(),
                    server_default=sa.text("0"),
                    nullable=True,
                ),
                sa.Column("locked_until", sa.DateTime(), nullable=True),
                sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            ),
        )

    user_indexes = _index_names(inspector, "users")
    if "idx_users_email" not in user_indexes:
        op.create_index("idx_users_email", "users", ["email"], unique=False)

    if not inspector.has_table("quiz_results"):
        op.create_table(
            "quiz_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("quiz_id", sa.String(length=255), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("total_questions", sa.Integer(), nullable=True),
            sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.ForeignKeyConstraint(
                ["username"],
                ["users.username"],
                name="fk_quiz_results_username_users",
                ondelete="CASCADE",
            ),
        )
    else:
        existing = _column_names(inspector, "quiz_results")
        _add_missing_columns(
            "quiz_results",
            existing,
            (
                sa.Column("quiz_id", sa.String(length=255), nullable=False, server_default=""),
                sa.Column("score", sa.Integer(), nullable=True),
                sa.Column("total_questions", sa.Integer(), nullable=True),
                sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    nullable=True,
                ),
                sa.Column("completed_at", sa.DateTime(), nullable=True),
                sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            ),
        )

        quiz_foreign_keys = _foreign_key_names(inspector, "quiz_results")
        if "fk_quiz_results_username_users" not in quiz_foreign_keys:
            op.create_foreign_key(
                "fk_quiz_results_username_users",
                "quiz_results",
                "users",
                ["username"],
                ["username"],
                ondelete="CASCADE",
            )

    quiz_indexes = _index_names(inspector, "quiz_results")
    if "idx_quiz_results_username" not in quiz_indexes:
        op.create_index("idx_quiz_results_username", "quiz_results", ["username"], unique=False)
    if "idx_quiz_results_quiz_id" not in quiz_indexes:
        op.create_index("idx_quiz_results_quiz_id", "quiz_results", ["quiz_id"], unique=False)
    if "idx_quiz_results_created_at" not in quiz_indexes:
        op.create_index("idx_quiz_results_created_at", "quiz_results", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("quiz_results"):
        quiz_indexes = _index_names(inspector, "quiz_results")
        for index_name in (
            "idx_quiz_results_created_at",
            "idx_quiz_results_quiz_id",
            "idx_quiz_results_username",
        ):
            if index_name in quiz_indexes:
                op.drop_index(index_name, table_name="quiz_results")
        op.drop_table("quiz_results")

    if inspector.has_table("users"):
        user_indexes = _index_names(inspector, "users")
        if "idx_users_email" in user_indexes:
            op.drop_index("idx_users_email", table_name="users")
        op.drop_table("users")
