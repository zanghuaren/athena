"""message question

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("question_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_messages_question_id_questions"),
        "messages",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 答疑里提取出的题目
    op.drop_constraint(op.f("ck_questions_source"), "questions", type_="check")
    op.create_check_constraint(
        op.f("ck_questions_source"),
        "questions",
        "source IN ('preset', 'scan', 'ask', 'ai', 'teacher', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_questions_source"), "questions", type_="check")
    op.create_check_constraint(
        op.f("ck_questions_source"),
        "questions",
        "source IN ('preset', 'scan', 'ai', 'teacher', 'manual')",
    )
    op.drop_constraint(op.f("fk_messages_question_id_questions"), "messages", type_="foreignkey")
    op.drop_column("messages", "question_id")
