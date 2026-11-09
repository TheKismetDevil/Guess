"""User model for authentication and platform identity."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_qq", "qq", unique=True,
                            postgresql_where=text("NOT legacy_duplicate_qq"),
                            sqlite_where=text("NOT legacy_duplicate_qq")),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    qq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    legacy_duplicate_qq: Mapped[bool] = mapped_column(Boolean, server_default=false())
    invite_code: Mapped[str] = mapped_column(String(8), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    score_change_logs_as_voter: Mapped[list["ScoreChangeLog"]] = relationship(
        foreign_keys="ScoreChangeLog.user_id",
        back_populates="user_rel",
    )
    score_change_logs_as_admin: Mapped[list["ScoreChangeLog"]] = relationship(
        foreign_keys="ScoreChangeLog.admin_user_id",
        back_populates="admin_user_rel",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
