"""Invite code business logic service (backed directly by the single ``users`` table)."""

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_score import HistoricalScore
from app.models.user import User
from app.models.vote import Vote
from app.schemas.invite_code import InviteCodeResponse
from app.services.placeholder_user_service import is_placeholder
from app.utils.invite_code import MAX_RETRIES, generate_invite_code


def _to_response(user: User) -> InviteCodeResponse:
    is_used = user.password_hash is not None
    return InviteCodeResponse(
        code=user.invite_code or "",
        status="used" if is_used else "unused",
        bound_username=user.username if is_used else None,
        bound_qq=user.qq,
        placeholder_username=user.username if is_placeholder(user) else None,
        created_at=user.created_at,
    )


async def _raise_if_existing_qq_blocks(db: AsyncSession, qq: str) -> User | None:
    user = (
        await db.execute(select(User).where(User.qq == qq).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        return None
    if user.is_admin or user.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "QQ_ALREADY_REGISTERED",
                "message": f"该 QQ 已注册用户「{user.username}」",
            },
        )
    if user.invite_code is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "QQ_HAS_UNUSED_CODE",
                "message": f"该 QQ 已有未使用的邀请码 {user.invite_code}",
            },
        )
    return user


async def get_invite_codes(
    db: AsyncSession, search: str | None = None
) -> list[InviteCodeResponse]:
    """Get all non-admin invite codes, optionally filtered by search term."""
    stmt = (
        select(User)
        .where(User.is_admin == False, User.invite_code.isnot(None))
        .order_by(User.created_at.desc(), User.id.desc())
    )

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                User.invite_code.ilike(search_term),
                User.username.ilike(search_term),
                User.qq.ilike(search_term),
            )
        )

    users = (await db.execute(stmt)).scalars().all()
    return [_to_response(u) for u in users]


async def create_invite_code(db: AsyncSession, qq: str) -> InviteCodeResponse:
    """Generate a unique invite code bound to the given QQ number.

    One QQ maps to at most one row in ``users``:
    - Registered user / admin -> 409 ``QQ_ALREADY_REGISTERED``
    - Unactivated row with an existing ``invite_code`` -> 409 ``QQ_HAS_UNUSED_CODE``
    - Unactivated row missing ``invite_code`` -> attaches generated code in place
    - New QQ -> inserts a pending ``User(qq=qq, invite_code=code, username=None, password_hash=None)``
    """
    existing = await _raise_if_existing_qq_blocks(db, qq)

    for _ in range(MAX_RETRIES):
        code_str = generate_invite_code()
        try:
            async with db.begin_nested():
                if existing is not None:
                    target = existing
                    target.invite_code = code_str
                else:
                    target = User(
                        username=None,
                        password_hash=None,
                        qq=qq,
                        invite_code=code_str,
                        is_admin=False,
                    )
                    db.add(target)
                await db.flush()
        except IntegrityError:
            await _raise_if_existing_qq_blocks(db, qq)
            if (
                await db.scalar(
                    select(User.id).where(User.invite_code == code_str)
                )
                is None
            ):
                raise
            continue

        await db.refresh(target)
        return _to_response(target)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "CODE_GENERATION_FAILED",
            "message": "无法生成唯一的邀请码，请重试",
        },
    )


async def delete_invite_code_cascade(db: AsyncSession, code: str) -> None:
    """Delete an invite code (and its User row + votes + historical scores).

    - Pending unused code (``username is None, password_hash is None``): deletes the row.
    - Historical placeholder (``username is not None, password_hash is None``): 409 ``PLACEHOLDER_PROTECTED``.
    - Registered user (``password_hash is not None``): deletes the user and cascades to votes & historical scores.
    """
    user = (
        await db.execute(
            select(User)
            .where(User.invite_code == code, User.is_admin == False)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "邀请码不存在"},
        )

    if is_placeholder(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PLACEHOLDER_PROTECTED",
                "message": "占位用户的邀请码不能删除，请等待对方注册",
            },
        )

    # Explicit deletes also work in SQLite unit tests where PRAGMA foreign_keys is off.
    await db.execute(delete(HistoricalScore).where(HistoricalScore.user_id == user.id))
    await db.execute(delete(Vote).where(Vote.user_id == user.id))
    await db.delete(user)
    await db.flush()
