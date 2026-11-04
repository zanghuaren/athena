from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'teacher')", name="role"),
        CheckConstraint("explain_mode IN ('guided', 'direct')", name="explain_mode"),
    )

    username: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    avatar: Mapped[str] = mapped_column(Text)
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    teach_subjects: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    teach_grades: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    explain_mode: Mapped[str | None] = mapped_column(Text)
    preferred_subject: Mapped[str | None] = mapped_column(Text)
    failed_logins: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# 用户名唯一按小写比较
Index("uq_users_username_lower", func.lower(User.username), unique=True)


class Session(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
