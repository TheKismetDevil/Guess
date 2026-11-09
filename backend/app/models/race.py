"""Race and RaceHorse models — race management with horse snapshot."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RaceStatus(str, enum.Enum):
    VOTING = "voting"
    LOCKED = "locked"
    SETTLED = "settled"


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    age_range: Mapped[str] = mapped_column(String(20), nullable=False)
    sex_restriction: Mapped[str] = mapped_column(String(20), nullable=False)
    race_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    distance: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[RaceStatus] = mapped_column(
        Enum(
            RaceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            constraint_name="ck_races_status",
            create_constraint=True,
        ),
        nullable=False,
        default=RaceStatus.VOTING,
        server_default=text("'voting'"),
    )
    custom_scoring: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    race_horses: Mapped[list["RaceHorse"]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )


class RaceHorse(Base):
    __tablename__ = "race_horses"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False, index=True
    )
    horse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("horses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jockey: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    race: Mapped["Race"] = relationship(back_populates="race_horses")
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="race_horse_rel", cascade="all, delete-orphan"
    )
