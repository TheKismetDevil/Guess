"""Tests for horse CRUD service and API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.main import app
from app.models.horse import Horse
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
        from fastapi import HTTPException

        from app.services.horse_service import create_horse

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

    @pytest.mark.asyncio
    async def test_origin_hemisphere_inheritance_backfill_and_conflict(
        self, db_session: AsyncSession
    ):
        from fastapi import HTTPException

        from app.schemas.horse import HorseUpdate
        from app.services.horse_service import create_horse, update_horse

        # Setting hemisphere without origin is rejected
        with pytest.raises(HTTPException) as no_origin_exc:
            await create_horse(
                db_session, HorseCreate(name="NoOrigin", hemisphere="north")
            )
        assert no_origin_exc.value.status_code == 400
        assert (
            no_origin_exc.value.detail["code"] == "ORIGIN_REQUIRED_FOR_HEMISPHERE"
        )

        # Trims origin/location whitespace; initial horse without hemisphere keeps None
        first = await create_horse(
            db_session,
            HorseCreate(name="FirstJP", origin=" 日本 ", location=" 栗东 "),
        )
        assert first.origin == "日本"
        assert first.location == "栗东"
        assert first.hemisphere is None

        # Setting hemisphere on a subsequent horse of the same origin backfills NULL rows
        second = await create_horse(
            db_session,
            HorseCreate(name="SecondJP", origin="日本", hemisphere="north"),
        )
        await db_session.refresh(first)
        assert second.hemisphere == "north"
        assert first.hemisphere == "north"

        # Subsequent horse with omitted hemisphere automatically inherits 'north'
        third = await create_horse(
            db_session, HorseCreate(name="ThirdJP", origin="日本")
        )
        assert third.hemisphere == "north"

        # Conflicting hemisphere on create or update is rejected with 409
        with pytest.raises(HTTPException) as create_conflict:
            await create_horse(
                db_session,
                HorseCreate(name="ConflictJP", origin="日本", hemisphere="south"),
            )
        assert create_conflict.value.status_code == 409
        assert (
            create_conflict.value.detail["code"] == "ORIGIN_HEMISPHERE_CONFLICT"
        )

        with pytest.raises(HTTPException) as update_conflict:
            await update_horse(
                db_session, third.id, HorseUpdate(hemisphere="south")
            )
        assert update_conflict.value.status_code == 409
        assert (
            update_conflict.value.detail["code"] == "ORIGIN_HEMISPHERE_CONFLICT"
        )

        # Moving a horse to another existing origin without hemisphere inherits target hemisphere
        aus = await create_horse(
            db_session,
            HorseCreate(name="AusHorse", origin="澳大利亚", hemisphere="south"),
        )
        assert aus.hemisphere == "south"
        moved = await update_horse(
            db_session, third.id, HorseUpdate(origin="澳大利亚")
        )
        assert moved.origin == "澳大利亚"
        assert moved.hemisphere == "south"

        # Clearing origin also clears hemisphere
        cleared = await update_horse(
            db_session, moved.id, HorseUpdate(origin=None)
        )
        assert cleared.origin is None
        assert cleared.hemisphere is None

    @pytest.mark.asyncio
    async def test_origins_stats_and_uniform_toggle_hemisphere(
        self, db_session: AsyncSession
    ):
        from fastapi import HTTPException

        from app.services.horse_service import (
            get_origins_stats,
            toggle_hemisphere,
        )

        with pytest.raises(HTTPException) as missing_exc:
            await toggle_hemisphere(db_session, "不存在")
        assert missing_exc.value.status_code == 404

        # Even if legacy/raw rows had mixed or NULL hemispheres, toggle unifies all of them
        h1 = Horse(name="Aus1", origin="澳大利亚", hemisphere="south")
        h2 = Horse(name="Aus2", origin="澳大利亚", hemisphere="south")
        h3 = Horse(name="Aus3", origin="澳大利亚", hemisphere="north")
        h4 = Horse(name="Aus4", origin="澳大利亚", hemisphere=None)
        jp = Horse(name="Jp1", origin="日本", hemisphere="north")
        db_session.add_all([h1, h2, h3, h4, jp])
        await db_session.flush()

        res1 = await toggle_hemisphere(db_session, "澳大利亚")
        assert res1 == {
            "origin": "澳大利亚",
            "new_hemisphere": "north",
            "affected_count": 4,
        }
        assert [h.hemisphere for h in (h1, h2, h3, h4)] == ["north"] * 4

        res2 = await toggle_hemisphere(db_session, "澳大利亚")
        assert res2["new_hemisphere"] == "south"
        assert [h.hemisphere for h in (h1, h2, h3, h4)] == ["south"] * 4

        stats = await get_origins_stats(db_session)
        assert stats == [
            {"origin": "澳大利亚", "count": 4, "hemisphere": "south"},
            {"origin": "日本", "count": 1, "hemisphere": "north"},
        ]


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
    async def test_origins_stats_and_toggle_hemisphere_api(
        self, db_session: AsyncSession
    ):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post(
                "/api/v1/horses",
                json={"name": "JP1", "origin": "日本", "hemisphere": "north"},
            )
            assert r1.status_code == 201

            conflict = await client.post(
                "/api/v1/horses",
                json={"name": "JP2", "origin": "日本", "hemisphere": "south"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["detail"]["code"] == "ORIGIN_HEMISPHERE_CONFLICT"

            toggle = await client.post("/api/v1/horses/origins/日本/toggle-hemisphere")
            assert toggle.status_code == 200
            assert toggle.json()["data"] == {
                "origin": "日本",
                "new_hemisphere": "south",
                "affected_count": 1,
            }

            stats = await client.get("/api/v1/horses/origins/stats")
            assert stats.status_code == 200
            assert stats.json()["data"] == [
                {"origin": "日本", "count": 1, "hemisphere": "south"}
            ]

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
