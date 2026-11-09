"""Tests for invite code utilities, service, and API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.utils.invite_code import generate_invite_code
from app.models.invite_code import InviteCode
from app.api.deps import get_current_admin


# --- In-memory SQLite test database ---

@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()


# --- Override dependencies for admin access ---

async def override_get_admin():
    return {"username": "admin", "is_admin": True}


# --- Utility Tests ---

class TestGenerateInviteCode:
    def test_code_length(self):
        code = generate_invite_code()
        assert len(code) == 8

    def test_code_characters(self):
        code = generate_invite_code()
        # All characters should be uppercase alphanumeric, no O/0/I/1
        for ch in code:
            assert ch.isalnum()
            assert ch.isupper() or ch.isdigit()
            assert ch not in "O0I1"

    def test_code_randomness(self):
        codes = {generate_invite_code() for _ in range(100)}
        assert len(codes) > 90  # High likelihood of uniqueness


# --- Service Tests ---

class TestInviteCodeService:
    @pytest.mark.asyncio
    async def test_create_and_list(self, db_session: AsyncSession):
        from app.services.invite_code_service import create_invite_code, get_invite_codes

        code = await create_invite_code(db_session, qq="12345678901")
        assert code.status == "unused"
        assert len(code.code) == 8

        codes = await get_invite_codes(db_session)
        assert len(codes) == 1

    @pytest.mark.asyncio
    async def test_search(self, db_session: AsyncSession):
        from app.services.invite_code_service import create_invite_code, get_invite_codes

        c1 = await create_invite_code(db_session, qq="12345")
        # Manually set bound fields for search testing
        row = (await db_session.execute(select(InviteCode).where(InviteCode.code == c1.code))).scalar_one()
        row.bound_username = "testuser"
        await db_session.flush()

        # Search by code
        results = await get_invite_codes(db_session, search=c1.code)
        assert len(results) >= 1

        # Search by username
        results = await get_invite_codes(db_session, search="testuser")
        assert len(results) >= 1

        # Search by qq
        results = await get_invite_codes(db_session, search="12345")
        assert len(results) >= 1

        # Search with no match
        results = await get_invite_codes(db_session, search="nonexistent")
        assert len(results) == 0


# --- API Tests ---

class TestInviteCodeAPI:
    @pytest.mark.asyncio
    async def test_list_codes(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/invite-codes")
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_code(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/admin/invite-codes", json={"qq": "12345678901"})
            assert resp.status_code == 201
            data = resp.json()
            assert data["data"]["status"] == "unused"
            assert len(data["data"]["code"]) == 8

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_code(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        from app.services.invite_code_service import get_invite_codes

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First create a code
            create_resp = await client.post("/api/v1/admin/invite-codes", json={"qq": "12345678901"})
            code = create_resp.json()["data"]["code"]

            # Then delete it
            resp = await client.delete(f"/api/v1/admin/invite-codes/{code}")
            assert resp.status_code == 204

            # Verify it is gone from the database
            codes = await get_invite_codes(db_session)
            assert not any(c.code == code for c in codes)

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/admin/invite-codes/NONEXIST")
            assert resp.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_search_codes(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a code and set bound fields
            from app.services.invite_code_service import create_invite_code
            c = await create_invite_code(db_session, qq="99999")
            row = (await db_session.execute(select(InviteCode).where(InviteCode.code == c.code))).scalar_one()
            row.bound_username = "founduser"
            await db_session.flush()

            # Search by username
            resp = await client.get("/api/v1/admin/invite-codes?search=founduser")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]) >= 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthorized_access(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/invite-codes")
            # Without override, no auth token → 401
            assert resp.status_code == 401
