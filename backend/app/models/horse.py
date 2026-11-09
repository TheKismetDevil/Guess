"""Horse model — horse data library with structured previous_result and best_win."""

from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Horse(Base):
    __tablename__ = "horses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hemisphere: Mapped[str | None] = mapped_column(String(10), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sire: Mapped[str | None] = mapped_column(String(100), nullable=True)
    damsire: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Previous result (last race performance) — structured fields
    previous_result: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_result_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    previous_result_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Best win (main victory) — structured fields
    best_win: Mapped[str | None] = mapped_column(String(100), nullable=True)
    best_win_date: Mapped[date | None] = mapped_column(Date, nullable=True)
