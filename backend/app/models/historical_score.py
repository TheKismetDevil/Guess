"""Historical import batches, snapshots, races, and user-linked scores."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HistoricalImportBatch(Base):
    __tablename__ = "historical_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    imported_races: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    imported_scores: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    updated_races: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HistoricalImportChange(Base):
    __tablename__ = "historical_import_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("historical_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    race_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)


class HistoricalRace(Base):
    __tablename__ = "historical_races"
    __table_args__ = (
        UniqueConstraint("name", "date", name="uq_historical_races_name_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("historical_import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    age_range: Mapped[str] = mapped_column(String(20), nullable=False)
    sex_restriction: Mapped[str] = mapped_column(String(20), nullable=False)
    race_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    surface: Mapped[str] = mapped_column(String(20), nullable=False)
    distance: Mapped[int] = mapped_column(Integer, nullable=False)
    horse_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class HistoricalScore(Base):
    __tablename__ = "historical_scores"
    __table_args__ = (
        UniqueConstraint("race_id", "user_id", name="uq_historical_scores_race_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(
        ForeignKey("historical_races.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped["User"] = relationship(back_populates="historical_scores")
