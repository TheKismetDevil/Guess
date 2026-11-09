"""Tests for horse CRUD service and API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.main import app
from app.schemas.horse import HorseCreate


# --- Override dependencies for admin access ---

async def override_get_admin():
    return {"username": "admin", "is_admin": True}


# --- Test Data ---

SAMPLE_HORSE = {
    "name": "Equinox",
    "sex": "牡",
    "birth_year": 2020,
    "origin": "日本",
    "sire": "Kitasan Black",
    "damsire": "Dance in the Dark",
    "previous_result": "1着",
    "best_win": "有马纪念(G1)",
}


# --- Service Tests ---

class TestHorseService:
    @pytest.mark.asyncio
    async def test_create_horse(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse, get_horses

        data = HorseCreate(**SAMPLE_HORSE)
        horse = await create_horse(db_session, data)
        assert horse.id is not None
        assert horse.name == "Equinox"
        assert horse.sex == "牡"
        assert horse.birth_year == 2020
        assert horse.origin == "日本"

        horses = await get_horses(db_session)
        assert len(horses) == 1

    @pytest.mark.asyncio
    async def test_create_horse_minimal(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse

        data = HorseCreate(name="TestHorse")
        horse = await create_horse(db_session, data)
        assert horse.name == "TestHorse"
        assert horse.sex is None
        assert horse.birth_year is None

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse
        from fastapi import HTTPException

        data = HorseCreate(name="Unique")
        await create_horse(db_session, data)

        with pytest.raises(HTTPException) as exc:
            await create_horse(db_session, HorseCreate(name="Unique"))
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_get_horses_list(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse, get_horses

        await create_horse(db_session, HorseCreate(name="A"))
        await create_horse(db_session, HorseCreate(name="B"))

        horses = await get_horses(db_session)
        assert len(horses) == 2

    @pytest.mark.asyncio
    async def test_search_horses_by_name(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse, get_horses

        await create_horse(db_session, HorseCreate(name="Equinox"))
        await create_horse(db_session, HorseCreate(name="Epiphaneia"))
        await create_horse(db_session, HorseCreate(name="Duramente"))

        results = await get_horses(db_session, name="Equi")
        assert len(results) == 1
        assert results[0].name == "Equinox"

        results = await get_horses(db_session, name="E")
        assert len(results) == 3  # All three start with or contain 'E'

        results = await get_horses(db_session, name="Nonexistent")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_horse_by_id(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse, get_horse

        created = await create_horse(db_session, HorseCreate(name="Test"))
        found = await get_horse(db_session, created.id)
        assert found is not None
        assert found.name == "Test"

    @pytest.mark.asyncio
    async def test_get_horse_not_found(self, db_session: AsyncSession):
        from app.services.horse_service import get_horse

        result = await get_horse(db_session, 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_horse(self, db_session: AsyncSession):
        from app.schemas.horse import HorseUpdate
        from app.services.horse_service import create_horse, update_horse

        created = await create_horse(db_session, HorseCreate(name="Original"))
        updated = await update_horse(
            db_session, created.id, HorseUpdate(name="Updated", birth_year=2022)
        )
        assert updated.name == "Updated"
        assert updated.birth_year == 2022
        assert updated.sex is None  # Unchanged

    @pytest.mark.asyncio
    async def test_update_horse_not_found(self, db_session: AsyncSession):
        from fastapi import HTTPException

        from app.schemas.horse import HorseUpdate
        from app.services.horse_service import update_horse

        with pytest.raises(HTTPException) as exc:
            await update_horse(db_session, 9999, HorseUpdate(name="New"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_horse_duplicate_name(self, db_session: AsyncSession):
        from fastapi import HTTPException

        from app.schemas.horse import HorseUpdate
        from app.services.horse_service import create_horse, update_horse

        await create_horse(db_session, HorseCreate(name="A"))
        b = await create_horse(db_session, HorseCreate(name="B"))

        with pytest.raises(HTTPException) as exc:
            await update_horse(db_session, b.id, HorseUpdate(name="A"))
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_horse(self, db_session: AsyncSession):
        from app.services.horse_service import create_horse, delete_horse, get_horse

        created = await create_horse(db_session, HorseCreate(name="ToDelete"))
        await delete_horse(db_session, created.id)

        found = await get_horse(db_session, created.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_horse_not_found(self, db_session: AsyncSession):
        from fastapi import HTTPException

        from app.services.horse_service import delete_horse

        with pytest.raises(HTTPException) as exc:
            await delete_horse(db_session, 9999)
        assert exc.value.status_code == 404


# --- API Tests ---

class TestHorseAPI:
    @pytest.mark.asyncio
    async def test_list_horses(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/horses")
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_horse_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/horses", json=SAMPLE_HORSE)
            assert resp.status_code == 201
            data = resp.json()
            assert data["data"]["name"] == "Equinox"
            assert data["data"]["sex"] == "牡"
            assert "manually_updated_fields" not in data["data"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_horse_minimal_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/horses", json={"name": "Minimal"})
            assert resp.status_code == 201
            data = resp.json()
            assert data["data"]["name"] == "Minimal"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_duplicate_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/horses", json={"name": "Dup"})
            resp = await client.post("/api/v1/horses", json={"name": "Dup"})
            assert resp.status_code == 409

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_horse_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/horses", json={"name": "GetMe"})
            horse_id = create_resp.json()["data"]["id"]

            resp = await client.get(f"/api/v1/horses/{horse_id}")
            assert resp.status_code == 200
            assert resp.json()["data"]["name"] == "GetMe"

            # Auto-protection reset endpoint was removed
            removed = await client.post(f"/api/v1/horses/{horse_id}/reset-auto-protection")
            assert removed.status_code in (404, 405)

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_horse_not_found_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/horses/9999")
            assert resp.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_search_horses_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/horses", json={"name": "SearchMe"})
            await client.post("/api/v1/horses", json={"name": "SearchYou"})

            resp = await client.get("/api/v1/horses?name=Search")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]) == 2

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_horse_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/horses", json={"name": "Old"})
            horse_id = create_resp.json()["data"]["id"]

            resp = await client.patch(
                f"/api/v1/horses/{horse_id}", json={"name": "New", "birth_year": 2021}
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["name"] == "New"
            assert data["birth_year"] == 2021

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_horse_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/horses", json={"name": "DeleteMe"})
            horse_id = create_resp.json()["data"]["id"]

            resp = await client.delete(f"/api/v1/horses/{horse_id}")
            assert resp.status_code == 204

            # Verify it's gone
            get_resp = await client.get(f"/api/v1/horses/{horse_id}")
            assert get_resp.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_create(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/horses", json={"name": "NoAuth"})
            assert resp.status_code == 401

        app.dependency_overrides.clear()
