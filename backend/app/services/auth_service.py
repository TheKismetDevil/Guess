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
from app.models.invite_code import InviteCode
from app.models.user import User
from app.services.avatar_service import avatar_key
from app.services.placeholder_user_service import find_placeholder
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


async def login(db: AsyncSession, request: LoginRequest) -> LoginResponse:
    """Authenticate user credentials and return JWT tokens.

    Supports three login modes:
    1. Username + password
    2. QQ + password
    3. Invite code (passwordless)

    Returns 401 for invalid credentials (no field-specific leak).
    """
    user = None

    # Mode 3: Invite code login (passwordless)
    if request.invite_code:
        result = await db.execute(
            select(InviteCode).where(InviteCode.code == request.invite_code)
        )
        invite_code = result.scalar_one_or_none()
        if invite_code is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "用户名或密码错误",
                },
            )
        if invite_code.status == "unused":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVITE_CODE_NOT_BOUND",
                    "message": "该邀请码尚未绑定用户",
                },
            )
        if invite_code.status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "用户名或密码错误",
                },
            )
        if invite_code.status == "used" and invite_code.bound_username:
            user_result = await db.execute(
                select(User).where(User.username == invite_code.bound_username)
            )
            user = user_result.scalar_one_or_none()

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
        result = await db.execute(
            select(User).where(User.qq == request.qq)
        )
        user = result.scalar_one_or_none()
        if user and not verify_password(request.password, user.password_hash):
            user = None

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
        user = result.scalar_one_or_none()
        if user and not verify_password(request.password, user.password_hash):
            user = None

    if user is None:
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
    """Validate refresh token and issue a new access token.

    Flow:
    1. Decode refresh_token and extract username (sub claim)
    2. Verify the user still exists in DB
    3. Generate a new access_token
    4. Return the new token

    Handles expired and invalid refresh tokens separately.
    """
    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username: str = payload.get("sub")
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

    # Verify user still exists
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "刷新令牌无效或已过期",
            },
        )

    # Generate new access_token
    access_token = create_access_token(data={"sub": username})

    return TokenRefreshResponse(access_token=access_token)


async def register(
    db: AsyncSession, request: RegisterRequest
) -> RegisterResponse:
    """Handle user registration with invite code validation.

    Flow:
    1. Look up invite code by code string
    2. Validate invite code status is "unused"
    3. Check username uniqueness
    4. Hash password, create User (or activate the QQ's placeholder user
       created by historical import), bind invite code
    5. Generate JWT tokens, return response
    """
    # Step 1: Look up invite code
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == request.invite_code)
    )
    invite_code = result.scalar_one_or_none()

    if invite_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_INVALID",
                "message": "邀请码无效或已被使用",
            },
        )

    # Step 2: Validate invite code status
    if invite_code.status == "used":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_USED",
                "message": "邀请码已被使用",
            },
        )

    if invite_code.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_INVALID",
                "message": "邀请码无效或已被使用",
            },
        )

    # Step 2.5: Validate QQ matches the bound QQ on the invite code
    if invite_code.bound_qq and invite_code.bound_qq != request.qq:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "QQ_MISMATCH",
                "message": "QQ 号与邀请码不匹配",
            },
        )

    # Step 3: One account per QQ; a placeholder created by historical import may be activated
    placeholder = await find_placeholder(db, request.qq)
    if placeholder is None:
        registered = (await db.execute(select(User.id).where(User.qq == request.qq))).first()
        if registered is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "QQ_ALREADY_REGISTERED",
                    "message": "该 QQ 已注册账户",
                },
            )

    # Step 3.5: Check username uniqueness (a placeholder being activated may keep its own name)
    existing_user = (await db.execute(
        select(User).where(User.username == request.username)
    )).scalar_one_or_none()
    if existing_user is not None and existing_user is not placeholder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "USERNAME_EXISTS",
                "message": "用户名已存在",
            },
        )

    # Step 4: Hash password
    password_hash = get_password_hash(request.password)

    # Step 5: Activate the placeholder created by historical import, or create a new User
    if placeholder is not None:
        user = placeholder
        user.username = request.username
        user.password_hash = password_hash
        user.invite_code = request.invite_code
    else:
        user = User(
            username=request.username,
            password_hash=password_hash,
            qq=request.qq,
            invite_code=request.invite_code,
            is_admin=False,
        )
        db.add(user)

    # Step 6: Bind invite code
    invite_code.status = "used"
    invite_code.bound_username = request.username
    invite_code.bound_qq = request.qq

    # Flush to get user.id before generating JWT
    # Catch IntegrityError for concurrent username duplicate registration
    try:
        await db.flush()
    except IntegrityError:
        # Rollback to allow re-use of the session
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "USERNAME_EXISTS",
                "message": "用户名已存在",
            },
        )

    # Step 7: Generate JWT tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return RegisterResponse(
        access_token=access_token,
        refresh_token=refresh_token,
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
    """Reset password using bound invite code verification.

    Flow:
    1. Look up invite_code by code string
    2. Verify invite_code is bound to a user (status == "used")
    3. Hash new password
    4. Update user's password_hash
    5. Return response with user info

    Returns 400 for all mismatch cases (no field-specific leak).
    """
    # Step 1: Look up invite code
    invite_result = await db.execute(
        select(InviteCode).where(InviteCode.code == request.invite_code)
    )
    invite_code = invite_result.scalar_one_or_none()

    if invite_code is None or invite_code.status != "used" or not invite_code.bound_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_MISMATCH",
                "message": "邀请码无效",
            },
        )

    # Step 2: Look up user by bound username
    result = await db.execute(
        select(User).where(User.username == invite_code.bound_username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVITE_CODE_MISMATCH",
                "message": "邀请码无效",
            },
        )

    # Step 3: Hash new password
    new_password_hash = get_password_hash(request.new_password)

    # Step 4: Update user's password_hash
    user.password_hash = new_password_hash
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
