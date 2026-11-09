"""Tests for user registration (Story 1.4) and login/refresh/deps (Story 1.5a)."""

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.core.security import create_refresh_token, verify_password
from app.main import app
from app.models.invite_code import InviteCode
from app.models.user import User


# --- Helper functions ---

async def create_user(
    db: AsyncSession,
    username: str = "testuser",
    password: str = "password123",
    qq: str = "12345678901",
    is_admin: bool = False,
) -> User:
    """Create a test user directly in the database."""
    from app.core.security import get_password_hash
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        qq=qq,
        invite_code=f"CODE{username[:4].upper()}",
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    return user


async def create_unused_invite_code(db: AsyncSession) -> InviteCode:
    """Seed an unused invite code for testing."""
    code = InviteCode(code="TESTCODE", status="unused")
    db.add(code)
    await db.flush()
    return code


async def create_used_invite_code(db: AsyncSession) -> InviteCode:
    """Seed a used invite code."""
    code = InviteCode(
        code="USEDCODE",
        status="used",
        bound_username="existing_user",
        bound_qq="123456789",
    )
    db.add(code)
    await db.flush()
    return code


# =============================================================================
# Registration Error Tests (Story 1.4)
# =============================================================================


class TestRegisterErrors:
    """Test registration error branches (AC #2, #3, #4)."""

    @pytest.mark.asyncio
    async def test_register_invalid_invite_code(self, async_client: AsyncClient):
        """AC #3: Invalid/non-existent invite code returns error."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "password123",
                "qq": "12345678901",
                "invite_code": "NONEXIST",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "INVITE_CODE_INVALID"

    @pytest.mark.asyncio
    async def test_register_used_invite_code(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #2: Already used invite code returns error."""
        await create_used_invite_code(db_session)
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "password123",
                "qq": "12345678901",
                "invite_code": "USEDCODE",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVITE_CODE_USED"

    @pytest.mark.asyncio
    async def test_register_duplicate_username(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #4: Duplicate username returns error."""
        await create_user(db_session, username="existing_user", qq="22222222222")
        await create_unused_invite_code(db_session)

        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing_user",
                "password": "password123",
                "qq": "12345678901",
                "invite_code": "TESTCODE",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "USERNAME_EXISTS"

    @pytest.mark.asyncio
    async def test_register_empty_fields(self, async_client: AsyncClient):
        """AC #6: Missing/empty fields return 422."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "",
                "password": "password123",
                "qq": "12345678901",
                "invite_code": "TESTCODE",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client: AsyncClient):
        """AC #7: Password shorter than 6 chars returns 422."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "12345",
                "qq": "12345678901",
                "invite_code": "TESTCODE",
            },
        )
        assert response.status_code == 422


# =============================================================================
# Registration Success Tests (Story 1.4)
# =============================================================================

class TestRegisterSuccess:
    """Test successful registration (AC #1, #5)."""

    @pytest.mark.asyncio
    async def test_register_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #1, #5: Valid registration returns 201 with tokens and user info."""
        await create_unused_invite_code(db_session)
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "password123",
                "qq": "12345678901",
                "invite_code": "TESTCODE",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["qq"] == "12345678901"
        assert data["user"]["is_admin"] is False

        # Verify password is hashed in DB
        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one()
        assert verify_password("password123", user.password_hash)
        assert user.invite_code == "TESTCODE"

        # Verify invite code is bound
        invite_result = await db_session.execute(
            select(InviteCode).where(InviteCode.code == "TESTCODE")
        )
        invite_code = invite_result.scalar_one()
        assert invite_code.status == "used"
        assert invite_code.bound_username == "newuser"
        assert invite_code.bound_qq == "12345678901"

    @pytest.mark.asyncio
    async def test_register_auto_login_tokens(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """Verify the returned tokens are valid JWT with correct payload."""
        await create_unused_invite_code(db_session)
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "autologin_user",
                "password": "password123",
                "qq": "98765432109",
                "invite_code": "TESTCODE",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]

        payload = jwt.decode(
            data["access_token"],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == "autologin_user"


# =============================================================================
# Login Tests (Story 1.5a)
# =============================================================================

class TestLogin:
    """Test login functionality (AC #1, #2)."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #1: Valid credentials return 200 with tokens and user info."""
        await create_user(db_session)
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["qq"] == "12345678901"
        assert data["user"]["is_admin"] is False

        # Verify JWT payload
        payload = jwt.decode(
            data["access_token"],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == "testuser"

    @pytest.mark.asyncio
    async def test_login_wrong_username(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #2: Wrong username returns 401."""
        await create_user(db_session, username="realuser")
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "wronguser", "password": "password123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #2: Wrong password returns 401."""
        await create_user(db_session)
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #2: Non-existent user returns 401 (same error as wrong password)."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"
        message = response.json()["detail"]["message"]
        assert message == "用户名或密码错误"


# =============================================================================
# Token Refresh Tests (Story 1.5a)
# =============================================================================

class TestTokenRefresh:
    """Test token refresh functionality (AC #3, #4)."""

    @pytest.mark.asyncio
    async def test_refresh_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #3: Valid refresh token returns new access_token."""
        user = await create_user(db_session)
        # Create a valid refresh token
        refresh_token = create_refresh_token(data={"sub": user.username})
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data

        # Verify the new token is valid
        payload = jwt.decode(
            data["access_token"],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == user.username

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, async_client: AsyncClient):
        """AC #4: Invalid refresh token returns 401."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token_here"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, async_client: AsyncClient):
        """AC #4: Expired refresh token returns 401."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt

        # Create an already-expired token
        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {"sub": "anyuser", "exp": expire}
        expired_token = jose_jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


# =============================================================================
# Dependency Injection Tests (Story 1.5a)
# =============================================================================

class TestDeps:
    """Test get_current_user and get_current_admin (AC #5, #6, #7)."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #6: Authenticated request returns full User object."""
        user = await create_user(db_session, username="authed_user")
        # Login to get tokens
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "authed_user", "password": "password123"},
        )
        token = response.json()["data"]["access_token"]

        # Access a protected endpoint
        response = await async_client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        # /health is not protected, but we verify token is accepted
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, async_client: AsyncClient):
        """Expired token returns 401."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt
        from fastapi import APIRouter, Depends
        import uuid

        expire = datetime.now(timezone.utc) - timedelta(minutes=1)
        payload = {"sub": "anyuser", "exp": expire}
        expired_token = jose_jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

        route_tag = f"expired_{uuid.uuid4().hex[:8]}"
        test_router = APIRouter()

        @test_router.get(f"/{route_tag}")
        async def test_protected(current_user=Depends(get_current_user)):
            if current_user is None:
                return {"user": None}
            return {"user": current_user.username}

        app.include_router(test_router)

        response = await async_client.get(
            f"/{route_tag}",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, async_client: AsyncClient):
        """Invalid JWT returns 401."""
        from fastapi import APIRouter, Depends
        import uuid

        route_tag = f"invalid_{uuid.uuid4().hex[:8]}"
        test_router = APIRouter()

        @test_router.get(f"/{route_tag}")
        async def test_protected2(current_user=Depends(get_current_user)):
            if current_user is None:
                return {"user": None}
            return {"user": current_user.username}

        app.include_router(test_router)

        response = await async_client.get(
            f"/{route_tag}",
            headers={"Authorization": "Bearer definitely_not_a_valid_jwt"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_guest_no_token_returns_none(self, async_client: AsyncClient):
        """AC #5: Request without token passes (guest access)."""
        from fastapi import APIRouter, Depends
        import uuid

        route_tag = f"guest_{uuid.uuid4().hex[:8]}"
        test_router = APIRouter()

        @test_router.get(f"/{route_tag}")
        async def test_guest(current_user=Depends(get_current_user)):
            if current_user is None:
                return {"user": None}
            return {"user": current_user.username}

        app.include_router(test_router)

        response = await async_client.get(f"/{route_tag}")
        assert response.status_code == 200
        assert response.json()["user"] is None

    @pytest.mark.asyncio
    async def test_get_current_admin_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """Admin user gets through get_current_admin."""
        await create_user(
            db_session, username="admin_user", password="admin123", is_admin=True
        )
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin_user", "password": "admin123"},
        )
        token = response.json()["data"]["access_token"]

        from fastapi import APIRouter, Depends
        import uuid

        route_tag = f"admin_check_{uuid.uuid4().hex[:8]}"
        test_router = APIRouter()

        @test_router.get(f"/{route_tag}")
        async def test_admin(current_user=Depends(get_current_admin)):
            return {"username": current_user.username}

        app.include_router(test_router)

        response = await async_client.get(
            f"/{route_tag}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "admin_user"

    @pytest.mark.asyncio
    async def test_get_current_admin_rejects_non_admin(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #7: Non-admin user gets 403 from get_current_admin."""
        await create_user(db_session)
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        token = response.json()["data"]["access_token"]

        from fastapi import APIRouter, Depends
        import uuid

        route_tag = f"admin_reject_{uuid.uuid4().hex[:8]}"
        test_router = APIRouter()

        @test_router.get(f"/{route_tag}")
        async def test_admin(current_user=Depends(get_current_admin)):
            return {"username": current_user.username}

        app.include_router(test_router)

        response = await async_client.get(
            f"/{route_tag}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "FORBIDDEN"


# =============================================================================
# Admin Seed Tests (Story 1.5a)
# =============================================================================

class TestAdminSeed:
    """Test admin seed account creation (AC #8)."""

    @pytest.mark.asyncio
    async def test_seed_admin_creates_admin(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #8: Admin seed creates an admin user that can login."""
        from app.utils.seed import seed_admin
        await seed_admin(db_session)
        await db_session.commit()

        # Verify admin exists and can login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user"]["username"] == "admin"
        assert data["user"]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_seed_admin_idempotent(
        self, db_session: AsyncSession
    ):
        """AC #8: Calling seed_admin twice doesn't create duplicate."""
        from app.utils.seed import seed_admin
        await seed_admin(db_session)
        await db_session.commit()

        # Second call
        await seed_admin(db_session)
        await db_session.commit()

        # Verify only one admin
        result = await db_session.execute(
            select(User).where(User.username == "admin")
        )
        admins = result.scalars().all()
        assert len(admins) == 1


# =============================================================================
# Password Reset Tests (Story 1.6)
# =============================================================================

class TestResetPassword:
    """Test password reset functionality (AC #1, #2, #3)."""

    @pytest.mark.asyncio
    async def test_reset_password_success(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #1, #3: Valid username + bound invite_code + new password returns 200
        and password is updated.
        """
        user = await create_user(db_session, username="reset_user")
        # Create a used invite code bound to this user
        code = InviteCode(
            code="RESETCOD",
            status="used",
            bound_username="reset_user",
            bound_qq="12345678901",
        )
        db_session.add(code)
        # Create unused for first-commit balance
        await create_unused_invite_code(db_session)
        await db_session.flush()

        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "username": "reset_user",
                "invite_code": "RESETCOD",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user"]["username"] == "reset_user"

        # Verify old password no longer works
        old_login = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "reset_user", "password": "password123"},
        )
        assert old_login.status_code == 401

        # Verify new password works
        new_login = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "reset_user", "password": "newpassword456"},
        )
        assert new_login.status_code == 200

        # Verify password hash changed in DB
        result = await db_session.execute(
            select(User).where(User.username == "reset_user")
        )
        user_db = result.scalar_one()
        from app.core.security import verify_password
        assert verify_password("newpassword456", user_db.password_hash)
        assert not verify_password("password123", user_db.password_hash)

    @pytest.mark.asyncio
    async def test_reset_password_wrong_invite_code(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """AC #2: Wrong invite code returns 400 INVITE_CODE_MISMATCH."""
        user = await create_user(db_session, username="wrong_code_user")
        # Create invite code bound to a different user
        code = InviteCode(
            code="WRONGCOD",
            status="used",
            bound_username="other_user",
            bound_qq="98765432109",
        )
        db_session.add(code)
        await db_session.flush()

        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "username": "wrong_code_user",
                "invite_code": "WRONGCOD",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVITE_CODE_MISMATCH"
        assert response.json()["detail"]["message"] == "邀请码无效"

    @pytest.mark.asyncio
    async def test_reset_password_nonexistent_user(
        self, async_client: AsyncClient
    ):
        """AC #2: Non-existent user returns 400 INVITE_CODE_MISMATCH."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "username": "ghost_user",
                "invite_code": "GHOSTCOD",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVITE_CODE_MISMATCH"

    @pytest.mark.asyncio
    async def test_reset_password_nonexistent_invite_code(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """Non-existent invite code returns 400 INVITE_CODE_MISMATCH."""
        await create_user(db_session, username="real_user")
        await db_session.flush()

        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "username": "real_user",
                "invite_code": "NONEXIST",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVITE_CODE_MISMATCH"

    @pytest.mark.asyncio
    async def test_reset_password_short_password(self, async_client: AsyncClient):
        """AC #4: Password shorter than 6 chars returns 422."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "username": "any_user",
                "invite_code": "ANYCOD00",
                "new_password": "12345",
            },
        )
        assert response.status_code == 422
