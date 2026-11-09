"""Placeholder accounts for historical QQ identities that have not registered yet.

Historical import creates or updates one placeholder ``User`` (``password_hash=None``,
``username`` set, ``invite_code`` set) for every QQ without a registered account.
When that person registers with the invite code, ``auth_service.register`` activates
the ``User`` row in place, so historical and live scores share one ``user_id``.
"""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models.historical_score import HistoricalScore
from app.models.user import User
from app.utils.invite_code import MAX_RETRIES, generate_invite_code

USERNAME_MAX_LENGTH = 50


def is_placeholder(user: User) -> bool:
    """Return True when the user is an unactivated historical placeholder."""
    return (
        not user.is_admin
        and user.password_hash is None
        and user.username is not None
    )


def unique_username(name: str, taken: set[str]) -> str:
    base = (name.strip() or "历史用户")[:USERNAME_MAX_LENGTH]
    candidate, suffix = base, 2
    while candidate in taken:
        tail = f"#{suffix}"
        candidate = base[: USERNAME_MAX_LENGTH - len(tail)] + tail
        suffix += 1
    taken.add(candidate)
    return candidate


def unique_code(taken: set[str]) -> str:
    while (code := generate_invite_code()) in taken:
        pass
    taken.add(code)
    return code


async def ensure_placeholders(db, people: dict[str, str]) -> int:
    """Ensure every QQ in ``people`` (qq -> display name) has a named User row.

    - If no ``User`` exists for ``qq``, creates a placeholder ``User`` with a
      generated ``invite_code``.
    - If an unnamed pending invite ``User`` (``username=None, password_hash=None``)
      already exists for ``qq``, promotes it to a placeholder by setting ``username``
      while keeping its existing ``invite_code``.
    - Registered users and already-named placeholders are left untouched.

    Returns the number of placeholder identities newly created/promoted.
    """
    if not people:
        return 0
    for attempt in range(MAX_RETRIES):
        try:
            async with db.begin_nested():
                return await _create_missing_placeholders(db, people)
        except IntegrityError:
            if attempt == MAX_RETRIES - 1:
                raise
    return 0


async def _create_missing_placeholders(db, people: dict[str, str]) -> int:
    existing_users = {
        u.qq: u
        for u in (
            await db.execute(select(User).where(User.qq.in_(people)))
        ).scalars()
    }
    to_create: list[tuple[str, str]] = []
    to_promote: list[tuple[User, str]] = []
    for qq, name in sorted(people.items()):
        user = existing_users.get(qq)
        if user is None:
            to_create.append((qq, name))
        elif not user.is_admin and user.password_hash is None and user.username is None:
            to_promote.append((user, name))

    if not to_create and not to_promote:
        return 0

    usernames = {
        u
        for u in (
            await db.execute(select(User.username).where(User.username.isnot(None)))
        ).scalars()
    }
    taken_codes = {
        c
        for c in (
            await db.execute(select(User.invite_code).where(User.invite_code.isnot(None)))
        ).scalars()
    }

    for user, name in to_promote:
        user.username = unique_username(name, usernames)
        if user.invite_code is None:
            user.invite_code = unique_code(taken_codes)

    for qq, name in to_create:
        db.add(
            User(
                username=unique_username(name, usernames),
                password_hash=None,
                qq=qq,
                invite_code=unique_code(taken_codes),
                is_admin=False,
            )
        )

    await db.flush()
    return len(to_create) + len(to_promote)


async def remove_orphan_placeholders(db) -> int:
    """Clear placeholder usernames whose User no longer has any historical score.

    The row's ``qq`` and ``invite_code`` are preserved as a normal unused invite code
    so a later re-import or registration can reuse the same code.
    """
    has_scores = (
        select(HistoricalScore.id)
        .where(HistoricalScore.user_id == User.id)
        .exists()
    )
    cleared = await db.scalars(
        update(User)
        .where(
            User.is_admin == False,
            User.password_hash.is_(None),
            User.username.isnot(None),
            ~has_scores,
        )
        .values(username=None)
        .returning(User.id)
    )
    return len(cleared.all())
