"""Invite code business logic service."""

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_score import HistoricalScore
from app.models.invite_code import InviteCode
from app.models.user import User
from app.schemas.invite_code import InviteCodeResponse
from app.services.placeholder_user_service import PLACEHOLDER_PASSWORD_PREFIX, is_placeholder
from app.utils.invite_code import generate_invite_code, MAX_RETRIES


def _placeholder_join():
    return and_(User.invite_code == InviteCode.code,
                User.password_hash.startswith(PLACEHOLDER_PASSWORD_PREFIX))


def _response(code: InviteCode, placeholder_username: str | None) -> InviteCodeResponse:
    return InviteCodeResponse.model_validate(code).model_copy(update={"placeholder_username": placeholder_username})


async def get_invite_codes(
    db: AsyncSession, search: str | None = None
) -> list[InviteCodeResponse]:
    """Get all invite codes (with placeholder usernames), optionally filtered by search term."""
    stmt = (
        select(InviteCode, User.username)
        .outerjoin(User, _placeholder_join())
        .order_by(InviteCode.created_at.desc(), InviteCode.id.desc())
    )

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                InviteCode.code.ilike(search_term),
                InviteCode.bound_username.ilike(search_term),
                InviteCode.bound_qq.ilike(search_term),
                User.username.ilike(search_term),
            )
        )

    result = await db.execute(stmt)
    return [_response(code, username) for code, username in result.all()]


async def create_invite_code(db: AsyncSession, qq: str) -> InviteCodeResponse:
    """Generate a unique invite code bound to the given QQ number.

    One QQ maps to exactly one account, so this refuses QQs that already have a
    registered user or a pending (unused) invite code. If the QQ only has a
    placeholder user without a code, the new code is attached to that placeholder.
    Retries up to MAX_RETRIES times if the generated code already exists.
    """
    user = (await db.execute(select(User).where(User.qq == qq))).scalar_one_or_none()
    if user is not None and not is_placeholder(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "QQ_ALREADY_REGISTERED", "message": f"该 QQ 已注册用户「{user.username}」"},
        )
    pending = (await db.execute(
        select(InviteCode).where(InviteCode.bound_qq == qq, InviteCode.status == "unused")
    )).scalars().first()
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "QQ_HAS_UNUSED_CODE", "message": f"该 QQ 已有未使用的邀请码 {pending.code}"},
        )

    for _ in range(MAX_RETRIES):
        code_str = generate_invite_code()
        existing = await db.execute(
            select(InviteCode).where(InviteCode.code == code_str)
        )
        if existing.scalar_one_or_none() is None:
            invite_code = InviteCode(code=code_str, bound_qq=qq)
            db.add(invite_code)
            if user is not None:
                user.invite_code = code_str
            await db.flush()
            await db.refresh(invite_code)
            return _response(invite_code, user.username if user is not None else None)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "CODE_GENERATION_FAILED",
            "message": "无法生成唯一的邀请码，请重试",
        },
    )


async def delete_invite_code_cascade(db: AsyncSession, code: str) -> None:
    """Delete an invite code and cascade delete its bound user, votes and historical scores.

    - Unused code: just deletes the invite code record.
    - Used code: also deletes the bound user (cascade deletes votes) and the
      historical scores recorded under the user's QQ.
    - Codes of placeholder users are protected and cannot be deleted.
    """
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code)
        .execution_options(populate_existing=True)
    )
    invite_code = result.scalar_one_or_none()

    if invite_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "邀请码不存在"},
        )

    placeholder = (await db.execute(select(User).where(
        User.invite_code == code, User.password_hash.startswith(PLACEHOLDER_PASSWORD_PREFIX)))).scalars().first()
    if placeholder is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PLACEHOLDER_PROTECTED", "message": "占位用户的邀请码不能删除，请等待对方注册"},
        )

    # If bound to a user, delete the user (cascade deletes votes) and their historical scores
    if invite_code.status == "used" and invite_code.bound_username:
        user_result = await db.execute(
            select(User).where(User.username == invite_code.bound_username)
        )
        user = user_result.scalar_one_or_none()
        if user:
            await db.execute(delete(HistoricalScore).where(HistoricalScore.qq == user.qq))
            await db.delete(user)

    # Delete the invite code
    await db.delete(invite_code)
    await db.flush()
