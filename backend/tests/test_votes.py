"""Tests for the voting system — Vote model, service, and API endpoints."""

from datetime import date

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.main import app
from app.models.horse import Horse
from app.models.race import Race, RaceStatus
from app.schemas.horse import HorseCreate
from app.schemas.race import RaceCreate
from app.services import vote_service
from app.services.race_service import create_race


# --- Override dependencies ---

async def override_get_admin():
    return type("AdminUser", (), {
        "id": 1,
        "username": "admin",
        "is_admin": True,
    })()


async def override_get_current_user():
    return type("CurrentUser", (), {
        "id": 2,
        "username": "testuser",
        "is_admin": False,
    })()


# --- Helpers ---

SAMPLE_HORSE = {"name": "Equinox"}
SAMPLE_HORSE_2 = {"name": "Epiphaneia"}
SAMPLE_HORSE_3 = {"name": "Duramente"}


async def _create_horse(db: AsyncSession, data: dict) -> Horse:
    horse = Horse(**HorseCreate(**data).model_dump())
    db.add(horse)
    await db.flush()
    await db.refresh(horse)
    return horse


async def _create_voting_race(
    db: AsyncSession, horse_ids: list[int] | None = None
) -> Race:
    if horse_ids is None:
        h1 = await _create_horse(db, SAMPLE_HORSE)
        h2 = await _create_horse(db, SAMPLE_HORSE_2)
        horse_ids = [h1.id, h2.id]
    return await create_race(
        db,
        RaceCreate(
            name="Test Race", date=date(2026, 6, 15),
            age_range="其他", sex_restriction="无", race_grade="G1",
            country="日本", distance=1200, surface="草地",
            horse_ids=horse_ids,
        ),
    )


# --- Service Tests ---

class TestVoteService:

    @pytest.mark.asyncio
    async def test_create_vote(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh = race.race_horses[0]

        vote, sc = await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh.id
        )
        assert sc == 201
        assert vote.id is not None
        assert vote.user_id == 2
        assert vote.race_id == race.id
        assert vote.race_horse_id == rh.id

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_update_vote(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh1 = race.race_horses[0]
        rh2 = race.race_horses[1]

        # Create first vote
        vote1, sc1 = await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh1.id
        )
        assert sc1 == 201
        assert vote1.race_horse_id == rh1.id

        # Update to different horse
        vote2, sc2 = await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh2.id
        )
        assert sc2 == 200
        # Same vote ID, updated race_horse_id
        assert vote2.id == vote1.id
        assert vote2.race_horse_id == rh2.id

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_vote_on_locked_race(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        race.status = RaceStatus.LOCKED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await vote_service.create_or_update_vote(
                db_session, race_id=race.id, user_id=2, race_horse_id=race.race_horses[0].id
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "VOTE_LOCKED"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_vote_on_settled_race(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await vote_service.create_or_update_vote(
                db_session, race_id=race.id, user_id=2, race_horse_id=race.race_horses[0].id
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "VOTE_LOCKED"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_vote_invalid_race_horse(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)

        # race_horse_id 99999 does not belong to this race
        with pytest.raises(HTTPException) as exc:
            await vote_service.create_or_update_vote(
                db_session, race_id=race.id, user_id=2, race_horse_id=99999
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "INVALID_HORSE"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_vote_non_existent_race(self, db_session: AsyncSession):
        with pytest.raises(HTTPException) as exc:
            await vote_service.create_or_update_vote(
                db_session, race_id=99999, user_id=2, race_horse_id=1
            )
        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_race_votes(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh1 = race.race_horses[0]
        rh2 = race.race_horses[1]

        # User 2 votes for first horse
        await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh1.id
        )
        # User 3 votes for second horse
        await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=3, race_horse_id=rh2.id
        )

        votes = await vote_service.get_race_votes(db_session, race.id)
        assert len(votes) == 2

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_lock_race(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)

        locked = await vote_service.lock_race(db_session, race.id)
        assert locked.status == RaceStatus.LOCKED

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_lock_already_locked_race(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        race.status = RaceStatus.LOCKED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await vote_service.lock_race(db_session, race.id)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "RACE_LOCKED"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_lock_settled_race(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        race.status = RaceStatus.SETTLED
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await vote_service.lock_race(db_session, race.id)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "RACE_SETTLED"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_lock_non_existent_race(self, db_session: AsyncSession):
        with pytest.raises(HTTPException) as exc:
            await vote_service.lock_race(db_session, 99999)
        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_race_vote_count(self, db_session: AsyncSession):
        from app.services.race_service import get_race_vote_count

        race = await _create_voting_race(db_session)
        rh1 = race.race_horses[0]

        # No votes yet
        count = await get_race_vote_count(db_session, race.id)
        assert count == 0

        # Add a vote
        await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh1.id
        )

        count = await get_race_vote_count(db_session, race.id)
        assert count == 1

        await db_session.rollback()


# --- API Tests ---

class TestVoteAPI:

    @pytest.mark.asyncio
    async def test_cast_vote_api(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh = race.race_horses[0]

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/races/{race.id}/votes",
                json={"race_horse_id": rh.id},
            )
            assert resp.status_code == 201
            data = resp.json()["data"]
            assert data["user_id"] == 2
            assert data["race_horse_id"] == rh.id

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_modify_vote_api(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh1 = race.race_horses[0]
        rh2 = race.race_horses[1]

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First vote
            resp1 = await client.post(
                f"/api/v1/races/{race.id}/votes",
                json={"race_horse_id": rh1.id},
            )
            assert resp1.status_code == 201

            # Modify to second horse
            resp2 = await client.post(
                f"/api/v1/races/{race.id}/votes",
                json={"race_horse_id": rh2.id},
            )
            assert resp2.status_code == 200
            assert resp2.json()["data"]["race_horse_id"] == rh2.id

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_vote_api(self, db_session: AsyncSession):
        """Test that unauthenticated POST /races/{id}/votes returns 401."""
        race = await _create_voting_race(db_session)
        rh = race.race_horses[0]

        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/races/{race.id}/votes",
                json={"race_horse_id": rh.id},
            )
            assert resp.status_code == 401
            assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_lock_race_api(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_admin] = override_get_admin
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/v1/races/{race.id}/lock")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["status"] == "locked"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_non_admin_lock_api(self, db_session: AsyncSession):
        """Test that non-admin POST /races/{id}/lock returns 403."""
        race = await _create_voting_race(db_session)

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/v1/races/{race.id}/lock")
            assert resp.status_code == 403

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_votes_api(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh1 = race.race_horses[0]

        await vote_service.create_or_update_vote(
            db_session, race_id=race.id, user_id=2, race_horse_id=rh1.id
        )

        app.dependency_overrides[get_db] = lambda: db_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/races/{race.id}/votes")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data) == 1
            assert data[0]["user_id"] == 2

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_vote_on_locked_race_api(self, db_session: AsyncSession):
        race = await _create_voting_race(db_session)
        rh = race.race_horses[0]
        race.status = RaceStatus.LOCKED
        await db_session.flush()

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/races/{race.id}/votes",
                json={"race_horse_id": rh.id},
            )
            assert resp.status_code == 400
            assert resp.json()["detail"]["code"] == "VOTE_LOCKED"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_vote_nonexistent_race_api(self, db_session: AsyncSession):
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/races/99999/votes",
                json={"race_horse_id": 1},
            )
            assert resp.status_code == 404

        app.dependency_overrides.clear()
