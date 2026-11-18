from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    wechat_openid_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(
        String(40),
        default="问道学友",
        nullable=False,
    )
    avatar_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class LoginSessionRecord(Base):
    __tablename__ = "login_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    __table_args__ = (Index("ix_login_sessions_user_id", "user_id"),)


class LearningRecord(Base):
    __tablename__ = "learning_records"

    quiz_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    quiz_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    answer_records: Mapped[list[dict] | None] = mapped_column(JSON)
    report_data: Mapped[dict | None] = mapped_column(JSON)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_learning_records_user_completed", "user_id", "completed_at"),
    )
