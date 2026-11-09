"""Authentication service — registration, login, token management."""

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserInfo,
)
from app.services.avatar_service import avatar_key


async def login(db: AsyncSession, request: LoginRequest) -> LoginResponse:
    """Authenticate user credentials and return JWT tokens.

    Supports three login modes:
    1. Username + password
    2. QQ + password
    3. Invite code (passwordless)

    Returns 401 for invalid credentials (no field-specific leak).
    """
    user: User | None = None

    # Mode 3: Invite code login (passwordless)
    if request.invite_code:
        result = await db.execute(
            select(User).where(
                User.invite_code == request.invite_code,
                User.is_admin == False,
            )
        )
        code_user = result.scalar_one_or_none()
        if code_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "用户名或密码错误",
                },
            )
        if code_user.password_hash is None or code_user.username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVITE_CODE_NOT_BOUND",
                    "message": "该邀请码尚未绑定用户",
                },
            )
        user = code_user

    # Mode 2: QQ + password
    elif request.qq:
        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "用户名或密码错误",
                },
            )
        result = await db.execute(select(User).where(User.qq == request.qq))
        candidate = result.scalar_one_or_none()
        if (
            candidate
            and candidate.username is not None
            and verify_password(request.password, candidate.password_hash)
        ):
            user = candidate

    # Mode 1: Username + password
    else:
        if not request.username or not request.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "用户名或密码错误",
                },
            )
        result = await db.execute(
            select(User).where(User.username == request.username)
        )
        candidate = result.scalar_one_or_none()
        if candidate and verify_password(request.password, candidate.password_hash):
            user = candidate

    if user is None or user.username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "用户名或密码错误",
            },
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token_val = create_refresh_token(data={"sub": user.username})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_val,
        user=UserInfo(
            id=user.id,
            username=user.username,
            qq=user.qq,
            is_admin=user.is_admin,
            avatar_key=avatar_key(user.qq),
        ),
    )


async def refresh_token(
    db: AsyncSession, request: TokenRefreshRequest
) -> TokenRefreshResponse:
    """Validate refresh token and issue a new access token."""
    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "刷新令牌无效或已过期",
                },
            )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "刷新令牌无效或已过期",
            },
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "刷新令牌无效或已过期",
            },
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "刷新令牌无效或已过期",
            },
        )

    access_token = create_access_token(data={"sub": username})
    return TokenRefreshResponse(access_token=access_token)


async def register(
    db: AsyncSession, request: RegisterRequest
) -> RegisterResponse:
    """Activate an unused invite / placeholder ``User`` row in place."""
    result = await db.execute(
        select(User)
        .where(User.invite_code == request.invite_code, User.is_admin == False)
        .with_for_update()
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_INVALID",
                "message": "邀请码无效或已被使用",
            },
        )

    if user.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_USED",
                "message": "邀请码已被使用",
            },
        )

    if user.qq != request.qq:
        # Check whether the requested QQ already belongs to a registered user or placeholder
        qq_owner = (
            await db.execute(select(User).where(User.qq == request.qq))
        ).scalar_one_or_none()
        if qq_owner is not None and (qq_owner.is_admin or qq_owner.password_hash is not None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "QQ_ALREADY_REGISTERED", "message": "该 QQ 已注册账户"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "QQ_MISMATCH",
                "message": "QQ 号与邀请码不匹配",
            },
        )

    # Check username uniqueness (a placeholder being activated may keep its own name)
    existing_user = (
        await db.execute(
            select(User).where(
                User.username == request.username,
                User.id != user.id,
            )
        )
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "USERNAME_EXISTS",
                "message": "用户名已存在",
            },
        )

    user.username = request.username
    user.password_hash = get_password_hash(request.password)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "USERNAME_EXISTS",
                "message": "用户名已存在",
            },
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token_val = create_refresh_token(data={"sub": user.username})

    return RegisterResponse(
        access_token=access_token,
        refresh_token=refresh_token_val,
        user=UserInfo(
            id=user.id,
            username=user.username,
            qq=user.qq,
            is_admin=user.is_admin,
            avatar_key=avatar_key(user.qq),
        ),
    )


async def reset_password(
    db: AsyncSession, request: ResetPasswordRequest
) -> ResetPasswordResponse:
    """Reset password using bound invite code verification."""
    result = await db.execute(
        select(User).where(
            User.invite_code == request.invite_code,
            User.is_admin == False,
        )
    )
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None or user.username is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_MISMATCH",
                "message": "邀请码无效",
            },
        )

    user.password_hash = get_password_hash(request.new_password)
    await db.flush()

    return ResetPasswordResponse(
        user=UserInfo(
            id=user.id,
            username=user.username,
            qq=user.qq,
            is_admin=user.is_admin,
            avatar_key=avatar_key(user.qq),
        ),
    )
