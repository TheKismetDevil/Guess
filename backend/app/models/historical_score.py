from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class HistoricalImportBatch(Base):
    __tablename__ = 'historical_import_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    imported_races: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_scores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_races: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistoricalImportChange(Base):
    __tablename__ = 'historical_import_changes'
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('historical_import_batches.id'), index=True)
    # Retain snapshots even after an original import is eventually removed.
    race_id: Mapped[int] = mapped_column(Integer, index=True)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)


class HistoricalRace(Base):
    __tablename__ = 'historical_races'
    __table_args__ = (UniqueConstraint('name', 'date'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey('historical_import_batches.id'), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    age_range: Mapped[str] = mapped_column(String(20), nullable=False)
    sex_restriction: Mapped[str] = mapped_column(String(20), nullable=False)
    race_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    surface: Mapped[str] = mapped_column(String(20), nullable=False)
    distance: Mapped[int] = mapped_column(Integer, nullable=False)
    horse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HistoricalScore(Base):
    __tablename__ = 'historical_scores'
    __table_args__ = (UniqueConstraint('race_id', 'qq'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey('historical_races.id', ondelete='CASCADE'), nullable=False)
    qq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
