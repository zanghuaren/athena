from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

SUBJECT_CHECK = "subject IN ('math', 'physics', 'english')"


class Chapter(IdMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (CheckConstraint(SUBJECT_CHECK, name="subject"),)

    code: Mapped[str] = mapped_column(Text, unique=True)
    subject: Mapped[str] = mapped_column(Text)
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    title: Mapped[str] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer)

    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        back_populates="chapter", order_by="KnowledgePoint.sort"
    )


class KnowledgePoint(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_points"

    chapter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    grades: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    sort: Mapped[int] = mapped_column(Integer)

    chapter: Mapped[Chapter] = relationship(back_populates="knowledge_points")
