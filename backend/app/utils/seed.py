"""Admin seed account creation (idempotent)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User


async def seed_admin(db: AsyncSession) -> None:
    """Create default admin account if not exists.

    This function is idempotent — if the admin user already exists,
    it does nothing. The default password is "admin123" and should
    be changed after first login.
    """
    result = await db.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none() is not None:
        return

    admin = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        qq="0000000000",
        invite_code=None,
        is_admin=True,
    )
    db.add(admin)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
