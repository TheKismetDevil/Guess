from datetime import date
from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class HistoricalRace(Base):
    __tablename__ = 'historical_races'
    __table_args__ = (UniqueConstraint('name', 'date'),)
    id: Mapped[int] = mapped_column(primary_key=True)
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
