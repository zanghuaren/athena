"""message image

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("image_file_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_messages_image_file_id_files"),
        "messages",
        "files",
        ["image_file_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_messages_image_file_id_files"), "messages", type_="foreignkey")
    op.drop_column("messages", "image_file_id")
