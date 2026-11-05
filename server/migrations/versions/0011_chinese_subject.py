"""chinese subject

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 2026-11-05 加入语文
_TABLES = ("chapters", "questions", "conversations", "scans")
_NEW = "subject IN ('chinese', 'math', 'physics', 'english')"
_OLD = "subject IN ('math', 'physics', 'english')"


def _replace(check: str) -> None:
    for table in _TABLES:
        op.drop_constraint(op.f(f"ck_{table}_subject"), table, type_="check")
        op.create_check_constraint(op.f(f"ck_{table}_subject"), table, check)


def upgrade() -> None:
    _replace(_NEW)


def downgrade() -> None:
    _replace(_OLD)
