"""Vote model — user votes for race entries."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True
    )
    race_horse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("race_horses.id"), nullable=False, index=True
    )
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "race_id", name="uq_vote_user_race"),
    )

    # Relationships
    race: Mapped["Race"] = relationship(back_populates="votes")
    user: Mapped["User"] = relationship(back_populates="votes")
    race_horse_rel: Mapped["RaceHorse"] = relationship(back_populates="votes")
