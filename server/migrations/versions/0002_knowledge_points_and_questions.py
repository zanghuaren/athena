"""knowledge points and questions

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chapters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
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
            "subject IN ('math', 'physics', 'english')", name=op.f("ck_chapters_subject")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapters")),
        sa.UniqueConstraint("code", name=op.f("uq_chapters_code")),
    )
    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("grades", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name=op.f("fk_knowledge_points_chapter_id_chapters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_points")),
        sa.UniqueConstraint("code", name=op.f("uq_knowledge_points_code")),
    )
    op.create_index(
        op.f("ix_knowledge_points_chapter_id"), "knowledge_points", ["chapter_id"], unique=False
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scoring_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("origin_question_id", sa.BigInteger(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
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
            "source IN ('preset', 'scan', 'ai', 'teacher', 'manual')",
            name=op.f("ck_questions_source"),
        ),
        sa.CheckConstraint(
            "subject IN ('math', 'physics', 'english')", name=op.f("ck_questions_subject")
        ),
        sa.CheckConstraint(
            "type IN ('single', 'multiple', 'judge', 'blank', 'solution', 'cloze', 'reading',"
            " 'essay')",
            name=op.f("ck_questions_type"),
        ),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name=op.f("ck_questions_difficulty")),
        sa.ForeignKeyConstraint(
            ["origin_question_id"],
            ["questions.id"],
            name=op.f("fk_questions_origin_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_questions_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_index(op.f("ix_questions_owner_id"), "questions", ["owner_id"], unique=False)
    op.create_table(
        "question_knowledge_points",
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_points.id"],
            name=op.f("fk_question_knowledge_points_knowledge_point_id_knowledge_points"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_question_knowledge_points_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "question_id", "knowledge_point_id", name=op.f("pk_question_knowledge_points")
        ),
    )
    op.create_index(
        op.f("ix_question_knowledge_points_knowledge_point_id"),
        "question_knowledge_points",
        ["knowledge_point_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_question_knowledge_points_knowledge_point_id"),
        table_name="question_knowledge_points",
    )
    op.drop_table("question_knowledge_points")
    op.drop_index(op.f("ix_questions_owner_id"), table_name="questions")
    op.drop_table("questions")
    op.drop_index(op.f("ix_knowledge_points_chapter_id"), table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_table("chapters")
