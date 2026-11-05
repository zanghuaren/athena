"""attempts

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answer_file_id", sa.BigInteger(), nullable=True),
        sa.Column("grading_status", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("max_score", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("grading_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("graded_by", sa.Text(), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("teacher_comment", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "error_reason IN ('concept', 'calculation', 'reading', 'method', 'careless', 'other')",
            name=op.f("ck_attempts_error_reason"),
        ),
        sa.CheckConstraint(
            "graded_by IN ('rule', 'ai', 'teacher')", name=op.f("ck_attempts_graded_by")
        ),
        sa.CheckConstraint(
            "grading_status IN ('pending', 'graded', 'manual')",
            name=op.f("ck_attempts_grading_status"),
        ),
        sa.CheckConstraint(
            "result IN ('correct', 'partial', 'wrong')", name=op.f("ck_attempts_result")
        ),
        sa.CheckConstraint(
            "source IN ('practice', 'variant', 'homework', 'scan', 'review')",
            name=op.f("ck_attempts_source"),
        ),
        sa.ForeignKeyConstraint(
            ["answer_file_id"],
            ["files.id"],
            name=op.f("fk_attempts_answer_file_id_files"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_attempts_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_attempts_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attempts")),
    )
    op.create_index(op.f("ix_attempts_question_id"), "attempts", ["question_id"], unique=False)
    op.create_index(
        "ix_attempts_source_source_id", "attempts", ["source", "source_id"], unique=False
    )
    op.create_index(
        "ix_attempts_student_id_counted_at", "attempts", ["student_id", "counted_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_attempts_student_id_counted_at", table_name="attempts")
    op.drop_index("ix_attempts_source_source_id", table_name="attempts")
    op.drop_index(op.f("ix_attempts_question_id"), table_name="attempts")
    op.drop_table("attempts")
