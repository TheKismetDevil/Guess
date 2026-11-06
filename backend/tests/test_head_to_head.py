from datetime import date

import pytest
from sqlalchemy import select

from app.api.deps import get_optional_user
from app.main import app
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.race import RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.services.head_to_head_service import compare, get_participants
from tests.test_leaderboard import leaderboard_data  # Shared settled-race fixture.


def user_key(user):
    return f'user:{user.id}'


async def historical_race(db, name, when, scores, **metadata):
    race = HistoricalRace(name=name, date=when, age_range='3岁', sex_restriction='无',
        race_grade='G1', country='日本', surface='草地', distance=1600, horse_count=12, **metadata)
    db.add(race)
    await db.flush()
    for qq, display_name, points in scores:
        db.add(HistoricalScore(race_id=race.id, qq=qq, display_name=display_name, points=points))
    await db.flush()
    return race


async def test_three_users_require_full_intersection_and_keep_column_order(db_session, leaderboard_data):
    data = leaderboard_data
    race = data['race1']
    race.is_hidden = False
    horse = (await db_session.execute(select(RaceHorse).where(RaceHorse.race_id == race.id))).scalars().first()
    db_session.add(Vote(user_id=data['user3'].id, race_id=race.id, race_horse_id=horse.id, points=-3))
    second = (await db_session.execute(select(Vote).where(Vote.race_id == race.id, Vote.user_id == data['user2'].id))).scalar_one()
    second.points = 0
    await db_session.flush()
    ids = [user_key(data[key]) for key in ('user2', 'user1', 'user3')]
    result = await compare(db_session, ids)
    assert [p['id'] for p in result['participants']] == ids
    assert len(result['races']) == 1
    assert result['races'][0]['name'] == 'Race 1'
    assert result['races'][0]['scores'] == [0, 10, -3]


async def test_live_and_history_are_combined_and_registered_qq_is_linked(db_session, leaderboard_data):
    data = leaderboard_data
    await historical_race(db_session, '历史共同赛', date(2026, 7, 1), [('10002', '旧昵称', 0), ('10003', '旧昵称2', -5)])
    await historical_race(db_session, '仅一人参加', date(2026, 7, 2), [('10002', '旧昵称', 20)])
    ids = [user_key(data['user1']), user_key(data['user2'])]
    result = await compare(db_session, ids, include_hidden=True)
    assert len(result['races']) == 3
    assert result['races'][0]['name'] == '历史共同赛'
    assert result['races'][0]['scores'] == [0, -5]
    assert len({r['key'] for r in result['races']}) == 3
    people = await get_participants(db_session)
    assert [p['username'] for p in people] == ['user1', 'user2', 'user3']
    assert all(set(p) == {'id', 'username', 'kind'} for p in people)


async def test_historical_only_users_and_all_race_filters(db_session, leaderboard_data):
    await historical_race(db_session, '共同赛', date(2026, 7, 1), [('10002', '旧昵称', 2), ('99999', 'user1', 7)])
    await historical_race(db_session, '较晚的比赛', date(2026, 7, 2), [('10002', '旧昵称', 10), ('99999', 'user1', 0)])
    people = await get_participants(db_session)
    historic = next(p for p in people if p['kind'] == 'historical')
    assert historic['username'] == 'user1'  # A matching nickname must not merge identities.
    assert '99999' not in historic['id']
    ids = [historic['id'], user_key(leaderboard_data['user1'])]
    filters = dict(age_range=['3岁'], sex_restriction=['无'], race_grade=['G1'], country=['日本'], surface=['草地'],
        distance_min=1600, distance_max=1600, horse_count_min=12, horse_count_max=12,
        date_from=date(2026, 7, 1), date_to=date(2026, 7, 1))
    result = await compare(db_session, ids, **filters)
    assert len(result['races']) == 1 and result['races'][0]['scores'] == [7, 2]
    assert (await compare(db_session, ids, country=['英国']))['races'] == []
    assert (await compare(db_session, ids, distance_min=1601))['races'] == []


async def test_unsettled_and_missing_points_are_not_treated_as_zero(db_session, leaderboard_data):
    data = leaderboard_data
    data['race1'].status = RaceStatus.LOCKED
    vote = (await db_session.execute(select(Vote).where(Vote.race_id == data['race2'].id, Vote.user_id == data['user2'].id))).scalar_one()
    vote.points = None
    await db_session.flush()
    assert (await compare(db_session, [user_key(data['user1']), user_key(data['user2'])]))['races'] == []


async def test_admin_and_ambiguous_qq_are_not_merged(db_session, leaderboard_data):
    db_session.add(User(username='重复QQ用户', qq='10002', password_hash='x', invite_code='QQDUP'))
    await historical_race(db_session, 'QQ重复赛', date(2026, 7, 1), [('10002', '历史独立身份', 3), ('10001', '管理员旧名', 99)])
    people = await get_participants(db_session)
    assert '管理员旧名' not in [p['username'] for p in people]
    assert user_key(leaderboard_data['admin']) not in [p['id'] for p in people]
    historic = next(p for p in people if p['kind'] == 'historical')
    assert historic['username'] == '历史独立身份'
    assert (await compare(db_session, [user_key(leaderboard_data['user1']), historic['id']]))['races'] == []


async def test_hidden_race_metadata_respects_viewer_permission(async_client, leaderboard_data):
    ids = [user_key(leaderboard_data['user1']), user_key(leaderboard_data['user2'])]
    public = await async_client.get('/api/v1/leaderboard/head-to-head', params={'participant_id': ids})
    assert public.status_code == 200
    assert all(r['name'] == '未公开比赛' and r['date'] == '' and r['id'] is None and r['key'].startswith('hidden:') for r in public.json()['data']['races'])
    app.dependency_overrides[get_optional_user] = lambda: leaderboard_data['admin']
    admin = await async_client.get('/api/v1/leaderboard/head-to-head', params={'participant_id': ids, 'date_from': '2026-06-01', 'date_to': '2026-06-01', 'horse_count_min': 4, 'horse_count_max': 4})
    assert admin.status_code == 200
    assert [r['name'] for r in admin.json()['data']['races']] == ['Race 1']


async def test_public_api_rejects_invalid_selection_and_dates(async_client, leaderboard_data):
    people = await async_client.get('/api/v1/leaderboard/participants')
    assert people.status_code == 200 and len(people.json()['data']) == 3
    one = user_key(leaderboard_data['user1'])
    two = user_key(leaderboard_data['user2'])
    path = '/api/v1/leaderboard/head-to-head'
    assert (await async_client.get(path, params={'participant_id': [one]})).status_code == 422
    assert (await async_client.get(path, params={'participant_id': [one, one]})).status_code == 400
    assert (await async_client.get(path, params={'participant_id': [one, 'user:99999']})).status_code == 400
    assert (await async_client.get(path, params={'participant_id': [one, two], 'date_from': '2026-08-01', 'date_to': '2026-07-01'})).status_code == 400
