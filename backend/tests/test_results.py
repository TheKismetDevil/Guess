"""Tests for result entry and settlement service."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.schemas.result import ResultEntry, ResultPosition
from app.services import result_service


@pytest.fixture
async def seeded_race(db_session: AsyncSession) -> Race:
    """Create a locked race with 4 horses and 2 votes for testing."""
    admin = User(username="admin", password_hash="x", qq="10001", invite_code=None, is_admin=True)
    user1 = User(username="user1", password_hash="x", qq="10002", invite_code="BBB")
    user2 = User(username="user2", password_hash="x", qq="10003", invite_code="CCC")
    db_session.add_all([admin, user1, user2])
    await db_session.flush()

    race = Race(
        name="Test Race",
        date=date(2026, 6, 15),
        age_range="其他",
        sex_restriction="无",
        race_grade="G1",
        country="日本",
        distance=1200,
        surface="草地",
        status=RaceStatus.LOCKED,
    )
    db_session.add(race)
    await db_session.flush()

    horses = []
    for i in range(4):
        rh = RaceHorse(
            race_id=race.id,
            horse_id=i + 1,
            snapshot_data={"name": f"Horse {i + 1}"},
            jockey=f"Jockey {i + 1}",
        )
        db_session.add(rh)
        horses.append(rh)
    await db_session.flush()

    vote1 = Vote(user_id=user1.id, race_id=race.id, race_horse_id=horses[0].id)
    vote2 = Vote(user_id=user2.id, race_id=race.id, race_horse_id=horses[1].id)
    db_session.add_all([vote1, vote2])
    await db_session.flush()

    await db_session.refresh(race, ["race_horses", "votes"])

    race._admin = admin
    race._user1 = user1
    race._user2 = user2
    race._horses = horses

    return race


@pytest.mark.asyncio
async def test_submit_results_fresh_settlement(db_session: AsyncSession, seeded_race: Race):
    """Test fresh settlement: locked → settled with correct points."""
    race = seeded_race
    horses = race._horses

    positions = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]
    data = ResultEntry(positions=positions)

    result = await result_service.submit_results(db_session, race.id, data)

    assert result["status"] == "settled"
    assert len(result["scores"]) == 2

    stmt = select(Race).where(Race.id == race.id)
    db_race = (await db_session.execute(stmt)).scalar_one()
    assert db_race.status == RaceStatus.SETTLED

    for rh in db_race.race_horses:
        expected_pos = next(p.position for p in positions if p.race_horse_id == rh.id)
        assert rh.position == expected_pos

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 10  # User1
    assert votes[1].points == 5   # User2


@pytest.mark.asyncio
async def test_submit_results_with_dnf(db_session: AsyncSession, seeded_race: Race):
    """Test settlement with a DNF horse."""
    race = seeded_race
    horses = race._horses

    positions = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=0),  # DNF
    ]
    data = ResultEntry(positions=positions)

    await result_service.submit_results(db_session, race.id, data)

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 10
    assert votes[1].points == 5


@pytest.mark.asyncio
async def test_submit_results_user_votes_dnf_horse(db_session: AsyncSession, seeded_race: Race):
    """Test user who voted for a DNF horse gets 0 points."""
    race = seeded_race
    horses = race._horses

    user2_id = race._user2.id
    stmt = select(Vote).where(Vote.user_id == user2_id, Vote.race_id == race.id)
    vote2 = (await db_session.execute(stmt)).scalar_one()
    vote2.race_horse_id = horses[3].id
    await db_session.flush()

    positions = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=0),  # DNF
    ]
    data = ResultEntry(positions=positions)

    await result_service.submit_results(db_session, race.id, data)

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 10
    assert votes[1].points == 0


@pytest.mark.asyncio
async def test_submit_results_resettle(db_session: AsyncSession, seeded_race: Race):
    """Test re-settlement of an already settled race."""
    race = seeded_race
    horses = race._horses

    positions1 = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]
    await result_service.submit_results(db_session, race.id, ResultEntry(positions=positions1))

    positions2 = [
        ResultPosition(race_horse_id=horses[0].id, position=2),
        ResultPosition(race_horse_id=horses[1].id, position=1),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]
    result = await result_service.submit_results(db_session, race.id, ResultEntry(positions=positions2))
    assert result["status"] == "settled"

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 5
    assert votes[1].points == 10


@pytest.mark.asyncio
async def test_submit_results_voting_race_rejected(db_session: AsyncSession):
    """Test that submitting results for a voting race returns error."""
    race = Race(
        name="Voting Race",
        date=date(2026, 6, 15),
        age_range="其他",
        sex_restriction="无",
        race_grade="G1",
        country="日本",
        distance=1200,
        surface="草地",
        status=RaceStatus.VOTING,
    )
    db_session.add(race)
    await db_session.flush()

    data = ResultEntry(positions=[ResultPosition(race_horse_id=999, position=1)])

    with pytest.raises(Exception) as exc_info:
        await result_service.submit_results(db_session, race.id, data)

    assert "RACE_NOT_LOCKED" in str(exc_info.value) or "400" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_results_race_not_found(db_session: AsyncSession):
    """Test that submitting results for a non-existent race returns error."""
    data = ResultEntry(positions=[ResultPosition(race_horse_id=1, position=1)])

    with pytest.raises(Exception) as exc_info:
        await result_service.submit_results(db_session, 99999, data)

    assert "NOT_FOUND" in str(exc_info.value) or "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_results_duplicate_positions_rejected(db_session: AsyncSession, seeded_race: Race):
    """Test that duplicate positive positions are rejected."""
    race = seeded_race
    horses = race._horses

    positions = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=1),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]

    with pytest.raises(Exception) as exc_info:
        ResultEntry(positions=positions)

    assert "Duplicate" in str(exc_info.value) or "duplicate" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_results_endpoint_integration(
    db_session: AsyncSession, async_client: AsyncClient, seeded_race: Race
):
    """Integration test for PUT /races/{id}/results (and verify removed history route)."""
    race = seeded_race
    horses = race._horses

    from app.api.deps import get_current_admin
    from app.main import app

    async def override_admin():
        return race._admin

    app.dependency_overrides[get_current_admin] = override_admin
    try:
        payload = {
            "positions": [
                {"race_horse_id": horses[0].id, "position": 1},
                {"race_horse_id": horses[1].id, "position": 2},
                {"race_horse_id": horses[2].id, "position": 3},
                {"race_horse_id": horses[3].id, "position": 4},
            ]
        }
        resp = await async_client.put(f"/api/v1/races/{race.id}/results", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "settled"
        assert len(data["scores"]) == 2

        removed = await async_client.get(f"/api/v1/races/{race.id}/results/history")
        assert removed.status_code in (404, 405)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resettle_dnf_change(db_session: AsyncSession, seeded_race: Race):
    """Test re-settlement involving DNF position changes."""
    race = seeded_race
    horses = race._horses

    await result_service.submit_results(
        db_session, race.id,
        ResultEntry(positions=[
            ResultPosition(race_horse_id=horses[0].id, position=1),
            ResultPosition(race_horse_id=horses[1].id, position=2),
            ResultPosition(race_horse_id=horses[2].id, position=3),
            ResultPosition(race_horse_id=horses[3].id, position=4),
        ]),
    )

    await result_service.submit_results(
        db_session, race.id,
        ResultEntry(positions=[
            ResultPosition(race_horse_id=horses[0].id, position=1),
            ResultPosition(race_horse_id=horses[1].id, position=2),
            ResultPosition(race_horse_id=horses[2].id, position=3),
            ResultPosition(race_horse_id=horses[3].id, position=0),
        ]),
    )

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 10
    assert votes[1].points == 5


@pytest.mark.asyncio
async def test_resettle_zero_votes(db_session: AsyncSession):
    """Test re-settlement when a race has no votes."""
    race = Race(
        name="Zero Vote Race", date=date(2026, 7, 1),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED,
    )
    db_session.add(race)
    await db_session.flush()

    horses = []
    for i in range(3):
        rh = RaceHorse(
            race_id=race.id, horse_id=i + 100,
            snapshot_data={"name": f"Horse {i + 1}"},
        )
        db_session.add(rh)
        horses.append(rh)
    await db_session.flush()

    positions = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
    ]
    result = await result_service.submit_results(db_session, race.id, ResultEntry(positions=positions))
    assert result["status"] == "settled"
    assert len(result["scores"]) == 0

    positions2 = [
        ResultPosition(race_horse_id=horses[0].id, position=3),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=1),
    ]
    result2 = await result_service.submit_results(db_session, race.id, ResultEntry(positions=positions2))
    assert result2["status"] == "settled"


@pytest.mark.asyncio
async def test_resettle_all_dnf(db_session: AsyncSession, seeded_race: Race):
    """Test re-settlement where all horses are DNF."""
    race = seeded_race
    horses = race._horses

    await result_service.submit_results(
        db_session, race.id,
        ResultEntry(positions=[
            ResultPosition(race_horse_id=horses[0].id, position=1),
            ResultPosition(race_horse_id=horses[1].id, position=2),
            ResultPosition(race_horse_id=horses[2].id, position=3),
            ResultPosition(race_horse_id=horses[3].id, position=4),
        ]),
    )

    await result_service.submit_results(
        db_session, race.id,
        ResultEntry(positions=[
            ResultPosition(race_horse_id=horses[0].id, position=0),
            ResultPosition(race_horse_id=horses[1].id, position=0),
            ResultPosition(race_horse_id=horses[2].id, position=0),
            ResultPosition(race_horse_id=horses[3].id, position=0),
        ]),
    )

    stmt = select(Vote).where(Vote.race_id == race.id).order_by(Vote.user_id)
    votes = (await db_session.execute(stmt)).scalars().all()
    assert votes[0].points == 0
    assert votes[1].points == 0
