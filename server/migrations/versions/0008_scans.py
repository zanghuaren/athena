"""scans

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("image_file_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default="processing", nullable=False),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("truncated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("total", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("correct", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("unknown", sa.SmallInteger(), server_default="0", nullable=False),
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
            "fail_reason IN ('unclear', 'no_question', 'error')", name=op.f("ck_scans_fail_reason")
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'done', 'failed')", name=op.f("ck_scans_status")
        ),
        sa.CheckConstraint(
            "subject IN ('math', 'physics', 'english')", name=op.f("ck_scans_subject")
        ),
        sa.ForeignKeyConstraint(
            ["image_file_id"],
            ["files.id"],
            name=op.f("fk_scans_image_file_id_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_scans_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_scans_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scans")),
    )
    op.create_index(
        "ix_scans_student_id_created_at", "scans", ["student_id", "created_at"], unique=False
    )
    op.create_table(
        "scan_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("scan_id", sa.BigInteger(), nullable=False),
        sa.Column("seq", sa.SmallInteger(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
            name=op.f("fk_scan_items_attempt_id_attempts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_scan_items_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.id"], name=op.f("fk_scan_items_scan_id_scans"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scan_items")),
        sa.UniqueConstraint("scan_id", "seq", name=op.f("uq_scan_items_scan_id")),
    )
    op.create_index(op.f("ix_scan_items_question_id"), "scan_items", ["question_id"], unique=False)
    # 拍照批改里学生可以自己确认“？”题的对错
    op.drop_constraint(op.f("ck_attempts_graded_by"), "attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_attempts_graded_by"),
        "attempts",
        "graded_by IN ('rule', 'ai', 'teacher', 'student')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_attempts_graded_by"), "attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_attempts_graded_by"), "attempts", "graded_by IN ('rule', 'ai', 'teacher')"
    )
    op.drop_index(op.f("ix_scan_items_question_id"), table_name="scan_items")
    op.drop_table("scan_items")
    op.drop_index("ix_scans_student_id_created_at", table_name="scans")
    op.drop_table("scans")
