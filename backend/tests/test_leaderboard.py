"""Tests for leaderboard service and endpoint."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.schemas.result import ResultEntry, ResultPosition
from app.services import result_service
from app.services.placeholder_user_service import ensure_placeholders


async def _add_historical_scores(
    db: AsyncSession, race_id: int, rows: list[tuple[str, str, int]]
) -> None:
    await ensure_placeholders(db, {qq: name for qq, name, _ in rows})
    users_by_qq = {
        u.qq: u.id
        for u in (
            await db.execute(select(User).where(User.qq.in_([qq for qq, _, _ in rows])))
        ).scalars()
    }
    for qq, _, points in rows:
        db.add(HistoricalScore(race_id=race_id, user_id=users_by_qq[qq], points=points))


@pytest.mark.asyncio
async def test_hidden_races_excluded_from_leaderboard_and_races_until_unhidden(
    async_client: AsyncClient, db_session: AsyncSession, leaderboard_data: dict
):
    from app.services.race_service import toggle_race_hidden

    race1 = leaderboard_data["race1"]
    race2 = leaderboard_data["race2"]

    # Hide race1 (4 horses, user1 +10, user2 +5); only race2 (user1 +10, user2 +5) remains public
    await toggle_race_hidden(db_session, race1.id)
    assert race1.is_hidden is True

    races_resp = (await async_client.get("/api/v1/leaderboard/races")).json()["data"]
    assert [r["name"] for r in races_resp] == ["Race 2"]

    ranking = (await async_client.get("/api/v1/leaderboard")).json()["data"]
    u1 = next(e for e in ranking if e["username"] == "user1")
    u2 = next(e for e in ranking if e["username"] == "user2")
    assert (u1["total_points"], u1["races_participated"], u1["avg_points"]) == (10, 1, 10.0)
    assert (u2["total_points"], u2["races_participated"], u2["avg_points"]) == (5, 1, 5.0)

    # Filtered query matching only hidden race1 must also exclude it
    filtered = (
        await async_client.get(
            "/api/v1/leaderboard",
            params={"horse_count_min": 4, "horse_count_max": 4},
        )
    ).json()["data"]
    assert all(e["races_participated"] == 0 and e["total_points"] == 0 for e in filtered)

    # Hide race2 as well -> zero public scored races, average mode threshold is 0 (0 races)
    await toggle_race_hidden(db_session, race2.id)
    assert (await async_client.get("/api/v1/leaderboard/races")).json()["data"] == []
    all_hidden_ranking = (await async_client.get("/api/v1/leaderboard")).json()["data"]
    assert all(e["races_participated"] == 0 and e["total_points"] == 0 for e in all_hidden_ranking)

    # Unhide race1 -> its settled scores immediately count again without re-settling
    await toggle_race_hidden(db_session, race1.id)
    unhidden_ranking = (await async_client.get("/api/v1/leaderboard")).json()["data"]
    u1_after = next(e for e in unhidden_ranking if e["username"] == "user1")
    assert (u1_after["total_points"], u1_after["races_participated"]) == (10, 1)


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
    """Create data for leaderboard tests: 3 users, 2 races, settled."""
    admin = User(username="admin", password_hash="x", qq="10001", invite_code=None, is_admin=True)
    user1 = User(username="user1", password_hash="x", qq="10002", invite_code="BBB")
    user2 = User(username="user2", password_hash="x", qq="10003", invite_code="CCC")
    user3 = User(username="user3", password_hash="x", qq="10004", invite_code="DDD")  # no votes
    db_session.add_all([admin, user1, user2, user3])
    await db_session.flush()

    # Race 1: G1, 4 horses
    race1 = Race(
        name="Race 1", date=date(2026, 6, 1),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED, is_hidden=False,
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

    v1r1 = Vote(user_id=user1.id, race_id=race1.id, race_horse_id=horses1[0].id)
    v2r1 = Vote(user_id=user2.id, race_id=race1.id, race_horse_id=horses1[1].id)
    db_session.add_all([v1r1, v2r1])
    await db_session.flush()
    await db_session.refresh(race1, ["race_horses", "votes"])

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
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED, is_hidden=False,
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

    v1r2 = Vote(user_id=user1.id, race_id=race2.id, race_horse_id=horses2[0].id)
    v2r2 = Vote(user_id=user2.id, race_id=race2.id, race_horse_id=horses2[1].id)
    db_session.add_all([v1r2, v2r2])
    await db_session.flush()
    await db_session.refresh(race2, ["race_horses", "votes"])

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
    assert len(entries) == 3

    assert entries[0].username == "user1"
    assert entries[0].total_points == 20
    assert entries[0].races_participated == 2
    assert entries[0].avg_points == 10.0

    assert entries[1].username == "user2"
    assert entries[1].total_points == 10
    assert entries[1].races_participated == 2
    assert entries[1].avg_points == 5.0


@pytest.mark.asyncio
async def test_leaderboard_users_without_votes(db_session: AsyncSession, leaderboard_data: dict):
    """Test: users with no votes appear with 0 values."""
    from app.services.leaderboard_service import get_leaderboard

    entries = await get_leaderboard(db_session)
    bottom_users = [e for e in entries if e.total_points == 0]
    assert len(bottom_users) == 1
    usernames = {e.username for e in bottom_users}
    assert "user3" in usernames


@pytest.mark.asyncio
async def test_leaderboard_tie_breaking(db_session: AsyncSession):
    """Test: tie in total_points → broken by avg_points desc."""
    from app.services.leaderboard_service import get_leaderboard

    admin = User(username="admin", password_hash="x", qq="10001", invite_code=None, is_admin=True)
    db_session.add(admin)
    await db_session.flush()

    race1 = Race(
        name="Race 1", date=date(2026, 6, 15),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED, is_hidden=False,
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

    pos1 = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=3),
        ResultPosition(race_horse_id=horses[3].id, position=4),
    ]
    await result_service.submit_results(db_session, race1.id, ResultEntry(positions=pos1))

    race2 = Race(
        name="Race 2", date=date(2026, 6, 16),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED, is_hidden=False,
    )
    db_session.add(race2)
    await db_session.flush()

    h2 = []
    for i in range(3):
        rh = RaceHorse(race_id=race2.id, horse_id=20 + i, snapshot_data={"name": f"R2-H{i+1}"})
        db_session.add(rh)
        h2.append(rh)
    await db_session.flush()

    v_b2 = Vote(user_id=user_b.id, race_id=race2.id, race_horse_id=h2[1].id)
    db_session.add(v_b2)
    await db_session.flush()
    await db_session.refresh(race2, ["race_horses", "votes"])

    pos2 = [
        ResultPosition(race_horse_id=h2[0].id, position=1),
        ResultPosition(race_horse_id=h2[1].id, position=2),
        ResultPosition(race_horse_id=h2[2].id, position=3),
    ]
    await result_service.submit_results(db_session, race2.id, ResultEntry(positions=pos2))

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

    admin = User(username="admin", password_hash="x", qq="30001", invite_code=None, is_admin=True)
    user = User(username="dnf_user", password_hash="x", qq="30002", invite_code="FFF")
    db_session.add_all([admin, user])
    await db_session.flush()

    race = Race(
        name="DNF Race", date=date(2026, 6, 15),
        age_range="其他", sex_restriction="无", race_grade="G1", country="日本", distance=1200, surface="草地",
        status=RaceStatus.LOCKED, is_hidden=False,
    )
    db_session.add(race)
    await db_session.flush()

    horses = []
    for i in range(3):
        rh = RaceHorse(race_id=race.id, horse_id=30 + i, snapshot_data={"name": f"H{i+1}"})
        db_session.add(rh)
        horses.append(rh)
    await db_session.flush()

    vote = Vote(user_id=user.id, race_id=race.id, race_horse_id=horses[2].id)
    db_session.add(vote)
    await db_session.flush()
    await db_session.refresh(race, ["race_horses", "votes"])

    pos = [
        ResultPosition(race_horse_id=horses[0].id, position=1),
        ResultPosition(race_horse_id=horses[1].id, position=2),
        ResultPosition(race_horse_id=horses[2].id, position=0),
    ]
    await result_service.submit_results(db_session, race.id, ResultEntry(positions=pos))

    entries = await get_leaderboard(db_session)
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

    assert data[0]["username"] == "user1"
    assert data[0]["total_points"] == 20
    assert data[0]["races_participated"] == 2
    assert data[0]["avg_points"] == 10.0


async def test_average_ranking_and_three_decimal_response(async_client, db_session):
    for index in range(3):
        race = HistoricalRace(name=f'平均分测试{index}', date=date(2026, 1, index + 1), age_range='3岁',
            sex_restriction='无', race_grade='G1' if index == 0 else 'G2', country='日本',
            surface='草地', distance=1600, horse_count=12)
        db_session.add(race)
        await db_session.flush()
        rows = [
            ('20002', '总分更高', 6),
            ('20003', '负分用户', -1 if index == 2 else 0),
        ]
        if index < 2:
            rows.append(('20001', '场均更高', 7))
        await _add_historical_scores(db_session, race.id, rows)
    await db_session.flush()
    base = '/api/v1/leaderboard'
    total = (await async_client.get(base)).json()['data']
    assert [e['username'] for e in total] == ['总分更高', '场均更高', '负分用户']
    average = (await async_client.get(base, params={'sort_by': 'avg_points'})).json()['data']
    assert [e['username'] for e in average] == ['场均更高', '总分更高', '负分用户']
    assert average[-1]['avg_points'] == -0.333
    filtered = (await async_client.get(base, params={'sort_by': 'avg_points', 'race_grade': 'G2'})).json()['data']
    assert [e['username'] for e in filtered] == ['总分更高', '负分用户']
    assert filtered[-1]['avg_points'] == -0.5
    assert (await async_client.get(base, params={'sort_by': 'invalid'})).status_code == 422


async def test_rounded_average_ties_are_sorted_using_exact_values(db_session):
    from app.services.leaderboard_service import get_leaderboard
    # 2/61 > 3/92; both display 0.033 and both exceed the 60% participation threshold.
    await ensure_placeholders(db_session, {'30001': '总分2', '30002': '总分3'})
    users_by_qq = {
        u.qq: u.id
        for u in (await db_session.execute(select(User).where(User.qq.in_(['30001', '30002'])))).scalars()
    }
    for index in range(92):
        race = HistoricalRace(name=f'精度测试{index}', date=date(2026, 1, 1), age_range='3岁',
            sex_restriction='无', race_grade='G1', country='日本', surface='草地', distance=1600, horse_count=12)
        db_session.add(race)
        await db_session.flush()
        db_session.add(HistoricalScore(race_id=race.id, user_id=users_by_qq['30002'], points=3 if index == 0 else 0))
        if index < 61:
            db_session.add(HistoricalScore(race_id=race.id, user_id=users_by_qq['30001'], points=2 if index == 0 else 0))
    await db_session.flush()
    entries = await get_leaderboard(db_session, sort_by='avg_points')
    assert [e.username for e in entries] == ['总分2', '总分3']
    assert [e.avg_points for e in entries] == [0.033, 0.033]


async def test_average_uses_combined_live_and_history_scores(async_client, db_session, leaderboard_data):
    race = HistoricalRace(name='旧成绩', date=date(2026, 1, 1), age_range='3岁', sex_restriction='无',
        race_grade='G1', country='日本', surface='草地', distance=1600, horse_count=12)
    db_session.add(race)
    await db_session.flush()
    await _add_historical_scores(db_session, race.id, [('10002', '旧昵称', 0)])
    await db_session.flush()
    result = (await async_client.get('/api/v1/leaderboard', params={'sort_by': 'avg_points'})).json()['data']
    person = next(e for e in result if e['username'] == 'user1')
    assert (person['total_points'], person['races_participated'], person['avg_points']) == (20, 3, 6.667)


async def test_average_participation_cutoff_uses_filtered_scored_races(async_client, db_session):
    db_session.add_all([
        User(username='管理员', password_hash='x', qq='90000', invite_code=None, is_admin=True),
        User(username='未参与', password_hash='x', qq='90001', invite_code='NONE'),
    ])
    await db_session.flush()
    for index in range(7):
        race = HistoricalRace(name=f'门槛测试{index}', date=date(2026, 2, index + 1), age_range='3岁',
            sex_restriction='无', race_grade='G1' if index < 3 else 'G2', country='日本',
            surface='草地', distance=1600, horse_count=12)
        db_session.add(race)
        await db_session.flush()
        rows = []
        if index < 5:
            rows.append(('91000', '参加5场', 1))
        if index < 3:
            rows.append(('91001', '恰好60%', 0))
        if index < 2:
            rows.append(('91002', '低于60%', 1000))
        if index == 5:
            rows.append(('90000', '管理员', 1000))
        await _add_historical_scores(db_session, race.id, rows)
    await db_session.flush()
    base = '/api/v1/leaderboard'
    total = (await async_client.get(base)).json()['data']
    assert total[0]['username'] == '低于60%'
    assert '未参与' in [e['username'] for e in total]
    races = (await async_client.get(base + '/races')).json()['data']
    assert len(races) == 5  # Empty and admin-only races are not in the ranking's denominator.
    averages = (await async_client.get(base, params={'sort_by': 'avg_points'})).json()['data']
    assert [e['username'] for e in averages] == ['参加5场', '恰好60%']
    assert averages[1]['races_participated'] == 3 and averages[1]['avg_points'] == 0
    filtered = (await async_client.get(base, params={'sort_by': 'avg_points', 'race_grade': 'G1'})).json()['data']
    assert filtered[0]['username'] == '低于60%'  # 2 out of 3 reaches ceil(1.8) = 2.
    assert len(filtered) == 3


async def test_average_denominator_is_distinct_races_not_max_user_participation(async_client, db_session):
    for index in range(5):
        race = HistoricalRace(name=f'各投一场{index}', date=date(2026, 3, index + 1), age_range='3岁',
            sex_restriction='无', race_grade='G1', country='日本', surface='草地', distance=1600, horse_count=12)
        db_session.add(race)
        await db_session.flush()
        await _add_historical_scores(db_session, race.id, [(f'9200{index}', f'选手{index}', 10)])
    await db_session.flush()
    base = '/api/v1/leaderboard'
    assert len((await async_client.get(base)).json()['data']) == 5
    assert (await async_client.get(base, params={'sort_by': 'avg_points'})).json()['data'] == []
    narrowed = (await async_client.get(base, params={'sort_by': 'avg_points', 'date_from': '2026-03-01', 'date_to': '2026-03-01'})).json()['data']
    assert [e['username'] for e in narrowed] == ['选手0']
