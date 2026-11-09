"""Placeholder accounts for historical QQ identities that have not registered yet.

Historical import creates one placeholder ``User`` (unusable password) plus an
unused invite code bound to the QQ for every QQ without an account. When that
person registers with the invite code, ``auth_service.register`` activates the
placeholder in place, so historical and live scores share one identity.
"""
import secrets

from sqlalchemy import select

from app.core.security import UNUSABLE_PASSWORD_PREFIX
from app.models.historical_score import HistoricalScore
from app.models.invite_code import InviteCode
from app.models.user import User
from app.utils.invite_code import generate_invite_code

PLACEHOLDER_PASSWORD_PREFIX = UNUSABLE_PASSWORD_PREFIX + 'placeholder:'
USERNAME_MAX_LENGTH = 50


def placeholder_password_hash() -> str:
    return PLACEHOLDER_PASSWORD_PREFIX + secrets.token_hex(16)


def is_placeholder(user: User) -> bool:
    return user.password_hash.startswith(PLACEHOLDER_PASSWORD_PREFIX)


async def find_placeholder(db, qq: str) -> User | None:
    users = (await db.execute(select(User).where(User.qq == qq))).scalars().all()
    return next((user for user in users if is_placeholder(user)), None)


def unique_username(name: str, taken: set[str]) -> str:
    base = (name.strip() or '历史用户')[:USERNAME_MAX_LENGTH]
    candidate, suffix = base, 2
    while candidate in taken:
        tail = f'#{suffix}'
        candidate = base[:USERNAME_MAX_LENGTH - len(tail)] + tail
        suffix += 1
    taken.add(candidate)
    return candidate


def unique_code(taken: set[str]) -> str:
    while (code := generate_invite_code()) in taken:
        pass
    taken.add(code)
    return code


async def ensure_placeholders(db, people: dict[str, str]) -> int:
    """Create placeholder users for QQs (qq -> display name) that have no account yet.

    Reuses an existing unused invite code bound to the QQ when there is one.
    Returns the number of placeholders created.
    """
    if not people:
        return 0
    existing = set((await db.execute(select(User.qq).where(User.qq.in_(people)))).scalars())
    missing = {qq: name for qq, name in people.items() if qq not in existing}
    if not missing:
        return 0
    usernames = set((await db.execute(select(User.username))).scalars())
    codes = list((await db.execute(select(InviteCode))).scalars())
    taken_codes = {c.code for c in codes}
    reusable = {c.bound_qq: c.code for c in codes if c.status == 'unused' and c.bound_qq in missing}
    for qq, name in sorted(missing.items()):
        code = reusable.get(qq)
        if code is None:
            code = unique_code(taken_codes)
            db.add(InviteCode(code=code, status='unused', bound_qq=qq))
        db.add(User(username=unique_username(name, usernames), password_hash=placeholder_password_hash(),
            qq=qq, invite_code=code, is_admin=False))
    await db.flush()
    return len(missing)


async def remove_orphan_placeholders(db) -> int:
    """Delete placeholders whose QQ no longer has any historical score (e.g. after undo).

    Their invite codes are kept so a later re-import or registration can reuse them.
    """
    placeholders = [u for u in (await db.execute(select(User).where(
        User.password_hash.startswith(PLACEHOLDER_PASSWORD_PREFIX)))).scalars()]
    if not placeholders:
        return 0
    scored = set((await db.execute(select(HistoricalScore.qq).where(
        HistoricalScore.qq.in_([u.qq for u in placeholders])).distinct())).scalars())
    orphans = [u for u in placeholders if u.qq not in scored]
    for user in orphans:
        await db.delete(user)
    await db.flush()
    return len(orphans)
