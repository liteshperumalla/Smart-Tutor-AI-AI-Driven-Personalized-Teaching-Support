"""Add version column for optimistic locking to users and student_mastery."""

from alembic import op
import sqlalchemy as sa


revision = "20261018_000003"
down_revision = "20260814_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("student_mastery", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("student_mastery", "version")
    op.drop_column("users", "version")
