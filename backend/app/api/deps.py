from datetime import datetime, timezone

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the current user from JWT token.

    - No token → returns None (guest access)
    - Valid token → queries DB and returns full User ORM object
    - Expired token → raises 401 TOKEN_EXPIRED
    - Invalid token → raises 401 INVALID_TOKEN
    - Valid token but user not found → raises 401 NOT_AUTHENTICATED
    """
    if credentials is None:
        return None  # Guest access

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "无效的令牌"},
            )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "登录已过期，请重新登录"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "无效的令牌"},
        )

    # Query DB for full User object
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "请先登录",
            },
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
):
    """Require admin privileges.

    Depends on get_current_user and checks the is_admin flag.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "请先登录"},
        )
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "需要管理员权限"},
        )
    return current_user


async def get_optional_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> Optional[User]:
    """Resolve the current user when a Bearer token is supplied, or None for guests.

    - No token → returns None (guest access on public endpoints)
    - Valid token → returns full User ORM object
    - Expired / invalid / unknown-user token → raises 401 (via get_current_user)
      so authenticated clients trigger silent token refresh or session cleanup
      instead of silently degrading to guest privileges.
    """
    return current_user
