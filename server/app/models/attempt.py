from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class Attempt(IdMixin, TimestampMixin, Base):
    """一次判分产生一条作答记录，是错题、复习和学情的唯一数据来源（KP-04）。"""

    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint(
            "source IN ('practice', 'variant', 'homework', 'scan', 'review')", name="source"
        ),
        CheckConstraint("grading_status IN ('pending', 'graded', 'manual')", name="grading_status"),
        CheckConstraint("result IN ('correct', 'partial', 'wrong')", name="result"),
        CheckConstraint("graded_by IN ('rule', 'ai', 'teacher')", name="graded_by"),
        CheckConstraint(
            "error_reason IN ('concept', 'calculation', 'reading', 'method', 'careless', 'other')",
            name="error_reason",
        ),
        Index("ix_attempts_student_id_counted_at", "student_id", "counted_at"),
        Index("ix_attempts_source_source_id", "source", "source_id"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(BigInteger)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    answer_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="SET NULL")
    )
    grading_status: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    grading_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    graded_by: Mapped[str | None] = mapped_column(Text)
    error_reason: Mapped[str | None] = mapped_column(Text)
    teacher_comment: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
