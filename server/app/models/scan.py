from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.attempt import Attempt
from app.models.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.models.file import File
from app.models.question import Question


class Scan(IdMixin, TimestampMixin, Base):
    """一次整页批改（SCAN-03）。"""

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'done', 'failed')", name="status"),
        CheckConstraint("fail_reason IN ('unclear', 'no_question', 'error')", name="fail_reason"),
        CheckConstraint("subject IN ('math', 'physics', 'english')", name="subject"),
        Index("ix_scans_student_id_created_at", "student_id", "created_at"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    image_file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="CASCADE")
    )
    job_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jobs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default="processing")
    fail_reason: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    total: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    correct: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    unknown: Mapped[int] = mapped_column(SmallInteger, server_default="0")

    # 列表和详情都要带原图地址
    image_file: Mapped[File] = relationship(lazy="selectin")


class ScanItem(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "scan_items"
    __table_args__ = (UniqueConstraint("scan_id", "seq"),)

    scan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scans.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(SmallInteger)
    bbox: Mapped[dict[str, float]] = mapped_column(JSONB)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("attempts.id", ondelete="SET NULL")
    )
    confidence: Mapped[float] = mapped_column(REAL)

    question: Mapped[Question] = relationship()
    attempt: Mapped[Attempt | None] = relationship()
