"""mistakes

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mistakes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("last_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("my_answer", sa.Text(), nullable=True),
        sa.Column("wrong_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("tip", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("review_stage", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("next_review_on", sa.Date(), nullable=True),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
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
            name=op.f("ck_mistakes_error_reason"),
        ),
        sa.CheckConstraint(
            "source IN ('ask', 'scan', 'practice', 'homework', 'manual')",
            name=op.f("ck_mistakes_source"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewing', 'mastered')", name=op.f("ck_mistakes_status")
        ),
        sa.CheckConstraint("char_length(note) <= 500", name=op.f("ck_mistakes_note")),
        sa.CheckConstraint("review_stage BETWEEN 0 AND 4", name=op.f("ck_mistakes_review_stage")),
        sa.ForeignKeyConstraint(
            ["last_attempt_id"],
            ["attempts.id"],
            name=op.f("fk_mistakes_last_attempt_id_attempts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_mistakes_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_mistakes_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mistakes")),
        sa.UniqueConstraint("student_id", "question_id", name=op.f("uq_mistakes_student_id")),
    )
    op.create_index(op.f("ix_mistakes_question_id"), "mistakes", ["question_id"], unique=False)
    op.create_index(
        "ix_mistakes_student_id_next_review_on",
        "mistakes",
        ["student_id", "next_review_on"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mistakes_student_id_next_review_on", table_name="mistakes")
    op.drop_index(op.f("ix_mistakes_question_id"), table_name="mistakes")
    op.drop_table("mistakes")
