from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from app.models.file import File
from app.models.knowledge import SUBJECT_CHECK


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(SUBJECT_CHECK, name="subject"),
        CheckConstraint("explain_mode IN ('guided', 'direct')", name="explain_mode"),
        Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),
        Index(
            "ix_conversations_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    explain_mode: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    turn_count: Mapped[int] = mapped_column(Integer, server_default="0")


class Message(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint("action IN ('hint', 'full', 'example')", name="action"),
        CheckConstraint("status IN ('done', 'interrupted', 'blocked')", name="status"),
        Index(
            "ix_messages_content_trgm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="done")
    image_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="SET NULL")
    )
    # 从这条讲解提取出的题目（加入错题本、练一道类似的）
    question_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="SET NULL")
    )
    # 返回消息时要带图片地址，查消息时一起查出来
    image_file: Mapped[File | None] = relationship(lazy="selectin")
