"""Add multi-course learning workspace tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260814_000002"
down_revision = "20260401_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("courses", sa.Column("id", sa.String(64), primary_key=True), sa.Column("code", sa.String(32), nullable=False, unique=True), sa.Column("title", sa.String(160), nullable=False), sa.Column("owner_username", sa.String(255)), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["owner_username"], ["users.username"], ondelete="SET NULL"))
    op.create_table("course_memberships", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("course_id", sa.String(64), nullable=False), sa.Column("username", sa.String(255), nullable=False), sa.Column("role", sa.String(32), nullable=False, server_default="student"), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["username"], ["users.username"], ondelete="CASCADE"), sa.UniqueConstraint("course_id", "username", name="uq_course_membership"))
    op.create_index("idx_course_memberships_username", "course_memberships", ["username"])
    op.create_table("learning_objectives", sa.Column("id", sa.String(128), primary_key=True), sa.Column("course_id", sa.String(64), nullable=False), sa.Column("module_id", sa.String(128), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())), sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"))
    op.create_index("idx_learning_objectives_course", "learning_objectives", ["course_id"])
    op.create_table("student_mastery", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("username", sa.String(255), nullable=False), sa.Column("course_id", sa.String(64), nullable=False), sa.Column("objective_id", sa.String(128), nullable=False), sa.Column("score", sa.Float(), nullable=False, server_default="0"), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())), sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["username"], ["users.username"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["objective_id"], ["learning_objectives.id"], ondelete="CASCADE"), sa.UniqueConstraint("username", "course_id", "objective_id", name="uq_student_mastery"))
    op.create_index("idx_student_mastery_course", "student_mastery", ["course_id"])


def downgrade() -> None:
    op.drop_table("student_mastery")
    op.drop_table("learning_objectives")
    op.drop_table("course_memberships")
    op.drop_table("courses")
