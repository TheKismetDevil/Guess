"""User model — unified platform identity, invite code, and placeholder lifecycle."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qq: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    invite_code: Mapped[str | None] = mapped_column(
        String(8), unique=True, nullable=True, index=True
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    historical_scores: Mapped[list["HistoricalScore"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
