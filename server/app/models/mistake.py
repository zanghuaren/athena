from datetime import date

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.attempt import Attempt
from app.models.base import Base, IdMixin, TimestampMixin
from app.models.question import Question


class Mistake(IdMixin, TimestampMixin, Base):
    """错题本（MIS），同一道题只入本一次，复习调度见技术方案 7.2。"""

    __tablename__ = "mistakes"
    __table_args__ = (
        UniqueConstraint("student_id", "question_id"),
        CheckConstraint(
            "source IN ('ask', 'scan', 'practice', 'homework', 'manual')", name="source"
        ),
        CheckConstraint("status IN ('pending', 'reviewing', 'mastered')", name="status"),
        CheckConstraint("review_stage BETWEEN 0 AND 4", name="review_stage"),
        CheckConstraint(
            "error_reason IN ('concept', 'calculation', 'reading', 'method', 'careless', 'other')",
            name="error_reason",
        ),
        CheckConstraint("char_length(note) <= 500", name="note"),
        Index("ix_mistakes_student_id_next_review_on", "student_id", "next_review_on"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(Text)
    last_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("attempts.id", ondelete="SET NULL")
    )
    my_answer: Mapped[str | None] = mapped_column(Text)
    wrong_count: Mapped[int] = mapped_column(Integer, server_default="1")
    error_reason: Mapped[str | None] = mapped_column(Text)
    tip: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    review_stage: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_review_on: Mapped[date | None] = mapped_column(Date)
    review_count: Mapped[int] = mapped_column(Integer, server_default="0")

    question: Mapped[Question] = relationship()
    last_attempt: Mapped[Attempt | None] = relationship()
