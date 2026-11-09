"""Tests for race CRUD service and API endpoints."""

from datetime import date, datetime

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_admin
from app.main import app
from app.models.horse import Horse
from app.models.race import RaceStatus
from app.schemas.horse import HorseCreate

# Default tag values for tests
_DEFAULT_TAGS = {
    "age_range": "其他",
    "sex_restriction": "无",
    "race_grade": "G1",
    "country": "日本",
    "distance": "1200m",
    "surface": "草地",
}


def _make_race_kwargs(**overrides) -> dict:
    """Build RaceCreate kwargs with default tag values."""
    kwargs = dict(_DEFAULT_TAGS)
    kwargs.update(overrides)
    return kwargs


def _make_race_json(name: str, date_str: str, **overrides) -> dict:
    """Build race JSON payload with default tag values."""
    payload = {
        "name": name,
        "date": date_str,
        "age_range": "其他",
        "sex_restriction": "无",
        "race_grade": "G1",
        "country": "日本",
        "distance": "1200m",
        "surface": "草地",
    }
    payload.update(overrides)
    return payload


# --- Override dependencies for admin access ---

async def override_get_admin():
    return type("AdminUser", (), {
        "id": 1,
        "username": "admin",
        "is_admin": True,
    })()


# --- Helpers ---

SAMPLE_HORSE = {
    "name": "Equinox",
    "sex": "牡",
    "birth_year": 2020,
    "origin": "日本",
    "sire": "Kitasan Black",
    "damsire": "Dance in the Dark",
    "weight": "520kg",
    "jockey": "C. Lemaire",
    "previous_result": "1着",
    "best_win": "有马纪念(G1)",
}

SAMPLE_HORSE_2 = {"name": "Epiphaneia"}
SAMPLE_HORSE_3 = {"name": "Duramente"}


async def _create_horse(db: AsyncSession, data: dict) -> Horse:
    """Helper: create a horse directly in the DB."""
    horse = Horse(**HorseCreate(**data).model_dump())
    db.add(horse)
    await db.flush()
    await db.refresh(horse)
    return horse


# --- Service Tests ---

class TestRaceService:

    @pytest.mark.asyncio
    async def test_create_race(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        data = RaceCreate(
            name="日本德比",
            date=date(2026, 6, 15),
            **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        )
        race = await create_race(db_session, data, creator_id=1)

        assert race.id is not None
        assert race.name == "日本德比"
        assert race.race_grade == "G1"
        assert race.age_range == "其他"
        assert race.sex_restriction == "无"
        assert race.country == "日本"
        assert race.distance == "1200m"
        assert race.status.value == "voting"
        assert len(race.race_horses) == 2

        # Verify snapshot data
        for rh in race.race_horses:
            assert rh.snapshot_data is not None
            assert rh.snapshot_data["name"] in ["Equinox", "Epiphaneia"]
            assert "sex" in rh.snapshot_data
            assert rh.position is None

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_create_race_custom_grade(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate, CustomScoring, PenaltyRule

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        data = RaceCreate(
            name="自定义测试",
            date=date(2026, 6, 20),
            **_make_race_kwargs(race_grade="自定义"),
            horse_ids=[h1.id, h2.id],
            custom_scoring=CustomScoring(
                positive_scores=[10, 7, 5, 3, 2, 1],
                penalty_rules=[PenaltyRule(position=-1, points=-5)],
            ),
        )
        race = await create_race(db_session, data, creator_id=1)

        assert race.custom_scoring is not None
        assert race.custom_scoring["positive_scores"] == [10, 7, 5, 3, 2, 1]
        assert race.custom_scoring["penalty_rules"] == [{"position": -1, "points": -5}]

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_create_race_insufficient_horses(self, db_session: AsyncSession):
        from app.schemas.race import RaceCreate
        from pydantic import ValidationError

        h1 = await _create_horse(db_session, SAMPLE_HORSE)

        with pytest.raises(ValidationError):
            RaceCreate(
                name="单人比赛",
                date=date(2026, 6, 15),
                **_make_race_kwargs(),
                horse_ids=[h1.id],
            )

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_get_races(self, db_session: AsyncSession):
        from app.services.race_service import create_race, get_races
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        h3 = await _create_horse(db_session, SAMPLE_HORSE_3)

        await create_race(db_session, RaceCreate(
            name="Race1", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        await create_race(db_session, RaceCreate(
            name="Race2", date=date(2026, 6, 20), **_make_race_kwargs(race_grade="G2"),
            horse_ids=[h2.id, h3.id],
        ), creator_id=1)

        races = await get_races(db_session, include_hidden=True)
        assert len(races) == 2

        # Test status filter
        races_voting = await get_races(db_session, status_filter="voting", include_hidden=True)
        assert len(races_voting) == 2

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_get_race(self, db_session: AsyncSession):
        from app.services.race_service import create_race, get_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="FindMe", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)

        found = await get_race(db_session, created.id)
        assert found is not None
        assert found.name == "FindMe"
        assert len(found.race_horses) == 2

        not_found = await get_race(db_session, 9999)
        assert not_found is None

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_race_name(self, db_session: AsyncSession):
        from app.services.race_service import create_race, get_race, update_race
        from app.schemas.race import RaceCreate, RaceUpdate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="Original", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)

        updated = await update_race(db_session, created.id, RaceUpdate(name="Updated"), user_id=1)
        assert updated.name == "Updated"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_delete_race(self, db_session: AsyncSession):
        from app.services.race_service import create_race, delete_race, get_race
        from app.schemas.race import RaceCreate
        from sqlalchemy import select

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="DeleteMe", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)

        await delete_race(db_session, created.id)

        found = await get_race(db_session, created.id)
        assert found is None

        # Verify cascade delete of race_horses
        from app.models.race import RaceHorse
        result = await db_session.execute(
            select(RaceHorse).where(RaceHorse.race_id == created.id)
        )
        remaining = result.scalars().all()
        assert len(remaining) == 0, "race_horses should be cascade-deleted"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_delete_race_settled(self, db_session: AsyncSession):
        from app.services.race_service import create_race, delete_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="SettledRace", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)

        # Manually set status to SETTLED to simulate settled race
        created.status = RaceStatus.SETTLED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await delete_race(db_session, created.id)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "RACE_SETTLED"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_delete_race_not_found(self, db_session: AsyncSession):
        from app.services.race_service import delete_race

        with pytest.raises(HTTPException) as exc_info:
            await delete_race(db_session, 99999)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "NOT_FOUND"

        await db_session.rollback()


# --- API Tests ---

class TestRaceAPI:

    @pytest.mark.asyncio
    async def test_list_races_api(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        await create_race(db_session, RaceCreate(
            name="API Race", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id], is_hidden=False,
        ), creator_id=1)

        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/races")
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data
            assert len(data["data"]) > 0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_race_api(self, db_session: AsyncSession):
        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/races", json=_make_race_json(
                "API日本德比", "2026-06-15",
                horse_ids=[h1.id, h2.id],
            ))
            assert resp.status_code == 201
            data = resp.json()
            assert data["data"]["name"] == "API日本德比"
            assert data["data"]["race_grade"] == "G1"
            assert data["data"]["age_range"] == "其他"
            assert data["data"]["sex_restriction"] == "无"
            assert data["data"]["country"] == "日本"
            assert data["data"]["distance"] == "1200m"
            assert data["data"]["status"] == "voting"
            assert len(data["data"]["horses"]) == 2

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_race_custom_api(self, db_session: AsyncSession):
        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/races", json=_make_race_json(
                "自定义API测试", "2026-06-20",
                race_grade="自定义",
                horse_ids=[h1.id, h2.id],
                custom_scoring={
                    "positive_scores": [10, 7, 5, 3, 2, 1],
                    "penalty_rules": [{"position": -1, "points": -5}],
                },
            ))
            assert resp.status_code == 201
            data = resp.json()
            assert data["data"]["custom_scoring"] is not None
            assert data["data"]["custom_scoring"]["positive_scores"] == [10, 7, 5, 3, 2, 1]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_race_detail_api(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/races", json=_make_race_json(
                "DetailTest", "2026-06-15",
                horse_ids=[h1.id, h2.id], is_hidden=False,
            ))
            race_id = create_resp.json()["data"]["id"]

            resp = await client.get(f"/api/v1/races/{race_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["name"] == "DetailTest"
            assert len(data["horses"]) == 2
            horse_names = [h["snapshot_data"]["name"] for h in data["horses"]]
            assert "Equinox" in horse_names

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_race_api(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/races", json=_make_race_json(
                "OldName", "2026-06-15",
                horse_ids=[h1.id, h2.id],
            ))
            race_id = create_resp.json()["data"]["id"]

            resp = await client.patch(f"/api/v1/races/{race_id}", json={
                "name": "NewName",
            })
            assert resp.status_code == 200
            assert resp.json()["data"]["name"] == "NewName"
            for dropped_grade in ("G3", "JPN2"):
                bad_patch = await client.patch(f"/api/v1/races/{race_id}", json={"race_grade": dropped_grade})
                assert bad_patch.status_code == 422
            ok_patch = await client.patch(f"/api/v1/races/{race_id}", json={"race_grade": "其他"})
            assert ok_patch.status_code == 200 and ok_patch.json()["data"]["race_grade"] == "其他"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_race_api(self, db_session: AsyncSession):
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/races", json=_make_race_json(
                "DeleteAPITest", "2026-06-15",
                horse_ids=[h1.id, h2.id],
            ))
            race_id = create_resp.json()["data"]["id"]

            resp = await client.delete(f"/api/v1/races/{race_id}")
            assert resp.status_code == 204

            get_resp = await client.get(f"/api/v1/races/{race_id}")
            assert get_resp.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_race_api(self, db_session: AsyncSession):
        """DELETE non-existent race → 404."""
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/races/99999")
            assert resp.status_code == 404
            data = resp.json()
            assert data["detail"]["code"] == "NOT_FOUND"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_settled_race_api(self, db_session: AsyncSession):
        """DELETE settled race → 400."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="SettledDelete", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        created.status = RaceStatus.SETTLED
        await db_session.flush()

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/races/{created.id}")
            assert resp.status_code == 400
            data = resp.json()
            assert data["detail"]["code"] == "RACE_SETTLED"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_locked_race_api(self, db_session: AsyncSession):
        """DELETE locked race → 204."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="LockedDelete", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        created.status = RaceStatus.LOCKED
        await db_session.flush()

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/races/{created.id}")
            assert resp.status_code == 204

            get_resp = await client.get(f"/api/v1/races/{created.id}")
            assert get_resp.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_delete_race_api(self, db_session: AsyncSession):
        """DELETE without admin auth → 401."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        created = await create_race(db_session, RaceCreate(
            name="NoAuthDelete", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)

        app.dependency_overrides[get_db] = lambda: db_session
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/races/{created.id}")
            assert resp.status_code == 401

        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/races", json=_make_race_json(
                "NoAuth", "2026-06-15",
                horse_ids=[1, 2],
            ))
            assert resp.status_code == 401

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_race_invalid_data_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Empty name
            resp = await client.post("/api/v1/races", json=_make_race_json(
                "", "2026-06-15",
                horse_ids=[1, 2],
            ))
            assert resp.status_code == 422

            # Invalid race_grade
            resp = await client.post("/api/v1/races", json={
                "name": "Test",
                "date": "2026-06-15",
                "age_range": "其他",
                "sex_restriction": "无",
                "race_grade": "INVALID",
                "country": "日本",
                "distance": "1200m",
                "horse_ids": [1, 2],
            })
            assert resp.status_code == 422

            # Single horse (and dropped race_grade values G3 / JPN2)
            for dropped_grade in ("G3", "JPN2"):
                dropped_resp = await client.post("/api/v1/races", json=_make_race_json("Test", "2026-06-15", race_grade=dropped_grade, horse_ids=[1, 2]))
                assert dropped_resp.status_code == 422
            resp = await client.post("/api/v1/races", json=_make_race_json(
                "Test", "2026-06-15",
                horse_ids=[1],
            ))
            assert resp.status_code == 422

        app.dependency_overrides.clear()


class TestRaceSettledResults:

    @pytest.mark.asyncio
    async def test_settled_race_horse_votes_grouped(self, db_session: AsyncSession):
        """Settled race — horses sorted by position, votes grouped correctly."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceHorse, RaceStatus
        from app.models.vote import Vote
        from app.models.user import User

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="SettledTest", date=date(2026, 6, 15), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        race_id = race.id

        race_horses = race.race_horses
        rh1 = race_horses[0]
        rh2 = race_horses[1]
        rh1.position = 1
        rh2.position = 2
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        user1 = User(username="user_a", password_hash="x", qq="111", invite_code="aaaa")
        user2 = User(username="user_b", password_hash="x", qq="222", invite_code="bbbb")
        db_session.add_all([user1, user2])
        await db_session.flush()

        vote1 = Vote(user_id=user1.id, race_id=race_id, race_horse_id=rh1.id, points=10)
        vote2 = Vote(user_id=user2.id, race_id=race_id, race_horse_id=rh2.id, points=5)
        db_session.add_all([vote1, vote2])
        await db_session.flush()

        from app.services.vote_service import get_race_results_grouped_by_horse
        result = await get_race_results_grouped_by_horse(db_session, race_id)

        assert len(result) == 2
        assert result[0]["position"] == 1
        assert result[1]["position"] == 2
        assert len(result[0]["votes"]) == 1
        assert result[0]["votes"][0]["username"] == "user_a"
        assert result[0]["votes"][0]["points"] == 10
        assert len(result[1]["votes"]) == 1
        assert result[1]["votes"][0]["username"] == "user_b"
        assert result[1]["votes"][0]["points"] == 5

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_settled_race_dnf_horse_last(self, db_session: AsyncSession):
        """Settled race — DNF horse listed last with 0-point votes."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceHorse, RaceStatus
        from app.models.vote import Vote
        from app.models.user import User

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="DNFTest", date=date(2026, 6, 20), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        race_id = race.id

        race_horses = race.race_horses
        rh1 = race_horses[0]
        rh2 = race_horses[1]
        rh1.position = 1
        rh2.position = 0  # DNF
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        user = User(username="voter", password_hash="x", qq="333", invite_code="cccc")
        db_session.add(user)
        await db_session.flush()

        vote = Vote(user_id=user.id, race_id=race_id, race_horse_id=rh2.id, points=0)
        db_session.add(vote)
        await db_session.flush()

        from app.services.vote_service import get_race_results_grouped_by_horse
        result = await get_race_results_grouped_by_horse(db_session, race_id)

        assert len(result) == 2
        assert result[0]["position"] == 1
        assert result[1]["position"] == 0
        assert result[1]["votes"][0]["points"] == 0

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_settled_race_horse_with_no_votes(self, db_session: AsyncSession):
        """Settled race — horse with zero votes shows empty votes list."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceHorse, RaceStatus

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="NoVotesHorse", date=date(2026, 6, 25), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        race_id = race.id

        race_horses = race.race_horses
        rh1 = race_horses[0]
        rh2 = race_horses[1]
        rh1.position = 1
        rh2.position = 2
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        from app.services.vote_service import get_race_results_grouped_by_horse
        result = await get_race_results_grouped_by_horse(db_session, race_id)

        assert len(result) == 2
        assert result[0]["votes"] == []
        assert result[1]["votes"] == []

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_settled_race_multiple_users_same_horse(self, db_session: AsyncSession):
        """Multiple users voted for same horse — all listed."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceHorse, RaceStatus
        from app.models.vote import Vote
        from app.models.user import User

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="MultiVote", date=date(2026, 7, 1), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id],
        ), creator_id=1)
        race_id = race.id

        race_horses = race.race_horses
        rh1 = race_horses[0]
        rh2 = race_horses[1]
        rh1.position = 1
        rh2.position = 2
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        users = []
        for i in range(3):
            u = User(username=f"user_{i}", password_hash="x", qq=f"qq{i}", invite_code=f"code{i}")
            db_session.add(u)
            users.append(u)
        await db_session.flush()

        for u in users:
            v = Vote(user_id=u.id, race_id=race_id, race_horse_id=rh1.id, points=10)
            db_session.add(v)
        await db_session.flush()

        from app.services.vote_service import get_race_results_grouped_by_horse
        result = await get_race_results_grouped_by_horse(db_session, race_id)

        assert len(result[0]["votes"]) == 3
        usernames = [v["username"] for v in result[0]["votes"]]
        assert "user_0" in usernames
        assert "user_1" in usernames
        assert "user_2" in usernames
        assert all(v["points"] == 10 for v in result[0]["votes"])

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_settled_race_api_horse_votes_field(self, db_session: AsyncSession):
        """API — settled race detail includes horse_votes field."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceStatus
        from app.models.vote import Vote
        from app.models.user import User

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="APISettled", date=date(2026, 7, 5), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id], is_hidden=False,
        ), creator_id=1)
        race_id = race.id

        race.race_horses[0].position = 1
        race.race_horses[1].position = 2
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        user = User(username="tester", password_hash="x", qq="555", invite_code="eeee")
        db_session.add(user)
        await db_session.flush()

        vote = Vote(user_id=user.id, race_id=race_id, race_horse_id=race.race_horses[0].id, points=10)
        db_session.add(vote)
        await db_session.flush()

        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/races/{race_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "horse_votes" in data
            assert "horses" in data["horse_votes"]
            assert len(data["horse_votes"]["horses"]) == 2
            assert len(data["horse_votes"]["horses"][0]["votes"]) == 1
            assert data["horse_votes"]["horses"][0]["votes"][0]["username"] == "tester"
            assert data["horse_votes"]["horses"][0]["votes"][0]["points"] == 10

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_voting_race_api_no_horse_votes(self, db_session: AsyncSession):
        """Voting race — horse_votes is null (not populated)."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(db_session, RaceCreate(
            name="VotingNoVotes", date=date(2026, 7, 10), **_make_race_kwargs(),
            horse_ids=[h1.id, h2.id], is_hidden=False,
        ), creator_id=1)
        race_id = race.id

        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/races/{race_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["horse_votes"] is None

        app.dependency_overrides.clear()



class TestRaceHorseManagement:
    """Tests for incremental horse management and gate ordering."""

    @pytest.mark.asyncio
    async def test_create_race_with_no_horses(self, db_session: AsyncSession):
        """Admin can create a race with zero horses."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        race = await create_race(
            db_session,
            RaceCreate(name="EmptyRace", date=date(2026, 8, 1), **_make_race_kwargs()),
            creator_id=1,
        )

        assert race.id is not None
        assert race.name == "EmptyRace"
        assert len(race.race_horses) == 0

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_add_horse_to_race(self, db_session: AsyncSession):
        """Add a single horse to a voting race via service."""
        from app.services.race_service import create_race, add_horse_to_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        h3 = await _create_horse(db_session, {"name": "NewHorse"})

        race = await create_race(
            db_session,
            RaceCreate(name="AddHorse", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )
        race_id = race.id

        rh = await add_horse_to_race(db_session, race_id, h3.id, weight="500kg", jockey="J. Moreira")
        assert rh.horse_id == h3.id
        assert rh.weight == "500kg"
        assert rh.jockey == "J. Moreira"
        assert rh.gate == 3

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_add_duplicate_horse_to_race(self, db_session: AsyncSession):
        """Adding a horse already in the race returns 400."""
        from app.services.race_service import create_race, add_horse_to_race
        from app.schemas.race import RaceCreate
        from fastapi import HTTPException

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(
            db_session,
            RaceCreate(name="DupHorse", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )

        with pytest.raises(HTTPException) as exc_info:
            await add_horse_to_race(db_session, race.id, h1.id)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "HORSE_ALREADY_IN_RACE"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_add_horse_to_locked_race(self, db_session: AsyncSession):
        """Adding a horse to a locked race returns 400."""
        from app.services.race_service import create_race, add_horse_to_race
        from app.schemas.race import RaceCreate
        from app.models.race import RaceStatus
        from fastapi import HTTPException

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        h3 = await _create_horse(db_session, {"name": "LateHorse"})

        race = await create_race(
            db_session,
            RaceCreate(name="LockedRace", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )
        race.status = RaceStatus.LOCKED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await add_horse_to_race(db_session, race.id, h3.id)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "RACE_NOT_EDITABLE"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_race_horse(self, db_session: AsyncSession):
        """Update per-race weight/jockey for a race horse."""
        from app.services.race_service import create_race, update_race_horse
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(
            db_session,
            RaceCreate(name="UpdateHorse", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )
        rh = race.race_horses[0]

        updated = await update_race_horse(db_session, race.id, rh.id, weight="510kg", jockey="Y. Kawada")
        assert updated.weight == "510kg"
        assert updated.jockey == "Y. Kawada"
        assert updated.snapshot_data["weight"] == "510kg"
        assert updated.snapshot_data["jockey"] == "Y. Kawada"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_gate_order(self, db_session: AsyncSession):
        """Update gate order for all horses in a race."""
        from app.services.race_service import create_race, update_gate_order
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        h3 = await _create_horse(db_session, {"name": "Third"})

        race = await create_race(
            db_session,
            RaceCreate(name="GateOrder", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id, h3.id]),
            creator_id=1,
        )
        rh_ids = [rh.id for rh in race.race_horses]

        new_order = list(reversed(rh_ids))
        updated = await update_gate_order(db_session, race.id, new_order)

        gate_map = {rh.id: rh.gate for rh in updated.race_horses}
        assert gate_map[new_order[0]] == 1
        assert gate_map[new_order[1]] == 2
        assert gate_map[new_order[2]] == 3

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_gate_order_incomplete(self, db_session: AsyncSession):
        """Gate order missing a horse returns 400."""
        from app.services.race_service import create_race, update_gate_order
        from app.schemas.race import RaceCreate
        from fastapi import HTTPException

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(
            db_session,
            RaceCreate(name="GateOrderBad", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )
        rh_ids = [rh.id for rh in race.race_horses]

        with pytest.raises(HTTPException) as exc_info:
            await update_gate_order(db_session, race.id, [rh_ids[0]])
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "INVALID_GATE_ORDER"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_add_race_horse_api(self, db_session: AsyncSession):
        """POST /api/v1/races/{id}/horses adds a horse."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)
        h3 = await _create_horse(db_session, {"name": "APIAdd"})

        race = await create_race(
            db_session,
            RaceCreate(name="APIAddHorse", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/v1/races/{race.id}/horses", json={
                "horse_id": h3.id,
                "weight": "505kg",
                "jockey": "K. Fujioka",
            })
            assert resp.status_code == 201
            data = resp.json()["data"]
            assert data["horse_id"] == h3.id
            assert data["weight"] == "505kg"
            assert data["jockey"] == "K. Fujioka"
            assert data["gate"] == 3

        app.dependency_overrides.clear()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_gate_order_api(self, db_session: AsyncSession):
        """PATCH /api/v1/races/{id}/horses/gate updates gate order."""
        from app.services.race_service import create_race
        from app.schemas.race import RaceCreate

        h1 = await _create_horse(db_session, SAMPLE_HORSE)
        h2 = await _create_horse(db_session, SAMPLE_HORSE_2)

        race = await create_race(
            db_session,
            RaceCreate(name="APIGate", date=date(2026, 8, 1), **_make_race_kwargs(), horse_ids=[h1.id, h2.id]),
            creator_id=1,
        )
        rh_ids = [rh.id for rh in race.race_horses]

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(f"/api/v1/races/{race.id}/horses/gate", json={
                "order": list(reversed(rh_ids)),
            })
            assert resp.status_code == 200
            data = resp.json()["data"]
            gate_map = {h["race_horse_id"]: h["gate"] for h in data["horses"]}
            assert gate_map[rh_ids[0]] == 2
            assert gate_map[rh_ids[1]] == 1

        app.dependency_overrides.clear()
        await db_session.rollback()
