from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.models.knowledge import SUBJECT_CHECK, KnowledgePoint


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(SUBJECT_CHECK, name="subject"),
        CheckConstraint(
            "type IN ('single', 'multiple', 'judge', 'blank', 'solution', 'cloze', 'reading',"
            " 'essay')",
            name="type",
        ),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty"),
        CheckConstraint("source IN ('preset', 'scan', 'ai', 'teacher', 'manual')", name="source"),
    )

    subject: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    analysis: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    scoring_points: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    origin_question_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="SET NULL")
    )
    content_text: Mapped[str] = mapped_column(Text)

    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        secondary="question_knowledge_points", order_by=KnowledgePoint.code
    )


class QuestionKnowledgePoint(CreatedAtMixin, Base):
    __tablename__ = "question_knowledge_points"

    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
