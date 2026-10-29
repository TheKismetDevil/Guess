"""Tests for leaderboard service and endpoint."""

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


@pytest.mark.asyncio
async def test_hidden_race_name_is_not_exposed(async_client, leaderboard_data):
    response = await async_client.get('/api/v1/leaderboard/races')
    assert response.status_code == 200
    assert len(response.json()['data']) == 2
    assert all(r['name'] == '未公开比赛' and r['date'] == '' and r['id'] is None for r in response.json()['data'])


@pytest.mark.asyncio
async def test_live_race_date_and_horse_count_match_leaderboard(async_client, leaderboard_data):
    params = {'date_from': '2026-06-01', 'date_to': '2026-06-01', 'horse_count_min': 4, 'horse_count_max': 4}
    ranking = (await async_client.get('/api/v1/leaderboard', params=params)).json()['data']
    races = (await async_client.get('/api/v1/leaderboard/races', params=params)).json()['data']
    assert len(races) == 1
    assert next(entry for entry in ranking if entry['username'] == 'user1')['races_participated'] == 1
    params['date_from'] = '2026-06-02'
    params['date_to'] = '2026-06-03'
    assert (await async_client.get('/api/v1/leaderboard/races', params=params)).json()['data'] == []
    assert all(entry['races_participated'] == 0 for entry in (await async_client.get('/api/v1/leaderboard', params=params)).json()['data'])


@pytest.fixture
async def leaderboard_data(db_session: AsyncSession) -> dict:
    """Create data for leaderboard tests: 3 users, 2 races, settled.

    Returns dict with references for assertions.
    """
    # Users
    admin = User(username="admin", password_hash="x", qq="10001", invite_code="AAA", is_admin=True)
    user1 = User(username="user1", password_hash="x", qq="10002", invite_code="BBB")
    user2 = User(username="user2", password_hash="x", qq="10003", invite_code="CCC")
    user3 = User(username="user3", password_hash="x", qq="10004", invite_code="DDD")  # no votes
    db_session.add_all([admin, user1, user2, user3])
    await db_session.flush()

    # Race 1: G1, 4 horses
    race1 = Race(
        name="Race 1", date=date(2026, 6, 1),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance="1200m", surface="草地",
        status=RaceStatus.LOCKED, creator_id=admin.id,
    )
    db_session.add(race1)
    await db_session.flush()

    horses1 = []
    for i in range(4):
        rh = RaceHorse(
            race_id=race1.id, horse_id=i + 1,
            snapshot_data={"name": f"H1-{i + 1}"},
        )
        db_session.add(rh)
        horses1.append(rh)
    await db_session.flush()

    # User1 votes horse1, User2 votes horse2
    v1r1 = Vote(user_id=user1.id, race_id=race1.id, race_horse_id=horses1[0].id)
    v2r1 = Vote(user_id=user2.id, race_id=race1.id, race_horse_id=horses1[1].id)
    db_session.add_all([v1r1, v2r1])
    await db_session.flush()
    await db_session.refresh(race1, ["race_horses", "votes"])

    # Settle race 1: horse1=1st(+10), horse2=2nd(+5)
    pos1 = [
        ResultPosition(race_horse_id=horses1[0].id, position=1),
        ResultPosition(race_horse_id=horses1[1].id, position=2),
        ResultPosition(race_horse_id=horses1[2].id, position=3),
        ResultPosition(race_horse_id=horses1[3].id, position=4),
    ]
    await result_service.submit_results(db_session, race1.id, ResultEntry(positions=pos1))

    # Race 2: G1, 3 horses
    race2 = Race(
        name="Race 2", date=date(2026, 6, 8),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance="1200m", surface="草地",
        status=RaceStatus.LOCKED, creator_id=admin.id,
    )
    db_session.add(race2)
    await db_session.flush()

    horses2 = []
    for i in range(3):
        rh = RaceHorse(
            race_id=race2.id, horse_id=10 + i,
            snapshot_data={"name": f"H2-{i + 1}"},
        )
        db_session.add(rh)
        horses2.append(rh)
    await db_session.flush()

    # User1 votes horse1, User2 votes horse2 (same pattern)
    v1r2 = Vote(user_id=user1.id, race_id=race2.id, race_horse_id=horses2[0].id)
    v2r2 = Vote(user_id=user2.id, race_id=race2.id, race_horse_id=horses2[1].id)
    db_session.add_all([v1r2, v2r2])
    await db_session.flush()
    await db_session.refresh(race2, ["race_horses", "votes"])

    # Settle race 2: horse1=1st(+10), horse2=2nd(+5)
    pos2 = [
        ResultPosition(race_horse_id=horses2[0].id, position=1),
        ResultPosition(race_horse_id=horses2[1].id, position=2),
        ResultPosition(race_horse_id=horses2[2].id, position=3),
    ]
    await result_service.submit_results(db_session, race2.id, ResultEntry(positions=pos2))

    return {
        "admin": admin, "user1": user1, "user2": user2, "user3": user3,
        "race1": race1, "race2": race2,
    }


@pytest.mark.asyncio
async def test_leaderboard_empty(db_session: AsyncSession):
    """Test: no settled races → empty leaderboard."""
    from app.services.leaderboard_service import get_leaderboard

    entries = await get_leaderboard(db_session)
    # Users who exist but have no points still appear with 0 totals
    # Since no users exist in this test, leaderboard is empty
    assert entries == []


@pytest.mark.asyncio
async def test_leaderboard_empty_with_users(db_session: AsyncSession):
    """Test: users exist but no settled races → all appear with 0 points."""
    from app.services.leaderboard_service import get_leaderboard

    user = User(username="lonely", password_hash="x", qq="99999", invite_code="ZZZ")
    db_session.add(user)
    await db_session.flush()

    entries = await get_leaderboard(db_session)
    assert len(entries) == 1
    assert entries[0].username == "lonely"
    assert entries[0].total_points == 0
    assert entries[0].races_participated == 0
    assert entries[0].avg_points == 0.0


@pytest.mark.asyncio
async def test_leaderboard_single_race(db_session: AsyncSession, leaderboard_data: dict):
    """Test: single race settled → users sorted by points."""
    from app.services.leaderboard_service import get_leaderboard

    entries = await get_leaderboard(db_session)
    # Admin excluded from leaderboard; only non-admin users
    assert len(entries) == 3

    # user1 should be first (20 points, avg=10)
    assert entries[0].username == "user1"
    assert entries[0].total_points == 20
    assert entries[0].races_participated == 2
    assert entries[0].avg_points == 10.0

    # user2 should be second (10 points, avg=5)
    assert entries[1].username == "user2"
    assert entries[1].total_points == 10
    assert entries[1].races_participated == 2
    assert entries[1].avg_points == 5.0


@pytest.mark.asyncio
async def test_leaderboard_users_without_votes(db_session: AsyncSession, leaderboard_data: dict):
    """Test: users with no votes appear with 0 values."""
    from app.services.leaderboard_service import get_leaderboard

    entries = await get_leaderboard(db_session)
    # Admin excluded from leaderboard; only user3 has no votes
    bottom_users = [e for e in entries if e.total_points == 0]
    assert len(bottom_users) == 1
    usernames = {e.username for e in bottom_users}
    assert "user3" in usernames


@pytest.mark.asyncio
async def test_leaderboard_tie_breaking(db_session: AsyncSession):
    """Test: tie in total_points → broken by avg_points desc.

    User A: 10pts from 1 race (avg=10.0)
    User B: 10pts from 2 races (avg=5.0)
    Same total, but User A higher avg → ranks higher.
    """
    from app.services.leaderboard_service import get_leaderboard

    admin = User(username="admin", password_hash="x", qq="10001", invite_code="AAA", is_admin=True)
    db_session.add(admin)
    await db_session.flush()

    # Race 1: G1, 4 horses — both users vote
    race1 = Race(
        name="Race 1", date=date(2026, 6, 15),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance="1200m", surface="草地",
        status=RaceStatus.LOCKED, creator_id=admin.id,
    )
    db_session.add(race1)
    await db_session.flush()

    horses = []
    for i in range(4):
        rh = RaceHorse(race_id=race1.id, horse_id=i + 1, snapshot_data={"name": f"H{i+1}"})
        db_session.add(rh)
        horses.append(rh)
    await db_session.flush()

    user_a = User(username="user_a", password_hash="x", qq="20001", invite_code="BBB")
    user_b = User(username="user_b", password_hash="x", qq="20002", invite_code="CCC")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    v_a1 = Vote(user_id=user_a.id, race_id=race1.id, race_horse_id=horses[0].id)
    v_b1 = Vote(user_id=user_b.id, race_id=race1.id, race_horse_id=horses[1].id)
    db_session.add_all([v_a1, v_b1])
    await db_session.flush()
    await db_session.refresh(race1, ["race_horses", "votes"])

    # Settle race 1: horse1=1st(+10 for user_a), horse2=2nd(+5 for user_b)
    pos1 = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]
    await result_service.submit_results(db_session, race1.id, ResultEntry(positions=pos1))

    # Race 2: G1, 3 horses — only user_b votes, gets 2nd position (+5)
    # Result: user_a=10pts(1 race avg=10), user_b=10pts(2 races avg=5)
    race2 = Race(
        name="Race 2", date=date(2026, 6, 16),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance="1200m", surface="草地",
        status=RaceStatus.LOCKED, creator_id=admin.id,
    )
    db_session.add(race2)
    await db_session.flush()

    h2 = []
    for i in range(3):
        rh = RaceHorse(race_id=race2.id, horse_id=20 + i, snapshot_data={"name": f"R2-H{i+1}"})
        db_session.add(rh)
        h2.append(rh)
    await db_session.flush()

    # user_b votes for h2[1] which will finish 2nd (+5pts)
    v_b2 = Vote(user_id=user_b.id, race_id=race2.id, race_horse_id=h2[1].id)
    db_session.add(v_b2)
    await db_session.flush()
    await db_session.refresh(race2, ["race_horses", "votes"])

    pos2 = [
        ResultPosition(race_horse_id=h2[0].id, position=1),
        ResultPosition(race_horse_id=h2[1].id, position=2),  # user_b's horse = 2nd → +5pts
        ResultPosition(race_horse_id=h2[2].id, position=3),
    ]
    await result_service.submit_results(db_session, race2.id, ResultEntry(positions=pos2))

    # Verify tie-breaking: same total (10), user_a higher avg → ranks first
    entries = await get_leaderboard(db_session)
    assert entries[0].username == "user_a", f"Expected user_a first, got {entries[0].username}"
    assert entries[0].total_points == 10
    assert entries[0].races_participated == 1
    assert entries[0].avg_points == 10.0

    assert entries[1].username == "user_b", f"Expected user_b second, got {entries[1].username}"
    assert entries[1].total_points == 10
    assert entries[1].races_participated == 2
    assert entries[1].avg_points == 5.0


@pytest.mark.asyncio
async def test_leaderboard_dnf_handling(db_session: AsyncSession):
    """Test: user voting for DNF horse gets 0 points, still appears in leaderboard."""
    from app.services.leaderboard_service import get_leaderboard

    admin = User(username="admin", password_hash="x", qq="30001", invite_code="EEE", is_admin=True)
    user = User(username="dnf_user", password_hash="x", qq="30002", invite_code="FFF")
    db_session.add_all([admin, user])
    await db_session.flush()

    race = Race(
        name="DNF Race", date=date(2026, 6, 15),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance="1200m", surface="草地",
        status=RaceStatus.LOCKED, creator_id=admin.id,
    )
    db_session.add(race)
    await db_session.flush()

    horses = []
    for i in range(3):
        rh = RaceHorse(race_id=race.id, horse_id=30 + i, snapshot_data={"name": f"H{i+1}"})
        db_session.add(rh)
        horses.append(rh)
    await db_session.flush()

    # User votes for horse3 (will be DNF)
    vote = Vote(user_id=user.id, race_id=race.id, race_horse_id=horses[2].id)
    db_session.add(vote)
    await db_session.flush()
    await db_session.refresh(race, ["race_horses", "votes"])

    # Settle: horse3 is DNF (position=0)
    pos = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=0),
    ]
    await result_service.submit_results(db_session, race.id, ResultEntry(positions=pos))

    entries = await get_leaderboard(db_session)
    # User should appear with 0 points, 1 race, 0.0 avg
    dnf_user = next(e for e in entries if e.username == "dnf_user")
    assert dnf_user.total_points == 0
    assert dnf_user.races_participated == 1
    assert dnf_user.avg_points == 0.0


@pytest.mark.asyncio
async def test_leaderboard_endpoint_unauthenticated(async_client: AsyncClient):
    """Test: unauthenticated access to leaderboard returns 200 (public)."""
    resp = await async_client.get("/api/v1/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_leaderboard_endpoint_integration(
    db_session: AsyncSession, async_client: AsyncClient, leaderboard_data: dict
):
    """Integration test: GET /api/v1/leaderboard returns correct data."""
    resp = await async_client.get("/api/v1/leaderboard")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3

    # First entry should be user1 (20pts)
    assert data[0]["username"] == "user1"
    assert data[0]["total_points"] == 20
    assert data[0]["races_participated"] == 2
    assert data[0]["avg_points"] == 10.0
