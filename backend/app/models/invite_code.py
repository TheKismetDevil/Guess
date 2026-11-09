"""InviteCode model for managing registration invite codes."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"
    _unused_bound = text("status = 'unused' AND bound_qq IS NOT NULL")
    __table_args__ = (Index("uq_invite_codes_unused_qq", "bound_qq", unique=True,
                            postgresql_where=_unused_bound, sqlite_where=_unused_bound),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(8), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unused"
    )

    bound_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bound_qq: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
