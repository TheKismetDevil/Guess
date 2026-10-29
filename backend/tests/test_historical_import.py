from io import BytesIO
from datetime import date
import pytest
from openpyxl import Workbook
from sqlalchemy import select
from fastapi import HTTPException
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.user import User
from app.services.historical_import_service import import_workbook
from app.services.leaderboard_service import get_leaderboard
from app.api.deps import get_current_admin
from app.main import app


def workbook(qq='12345'):
    w = Workbook()
    s = w.active
    s.title = '历史得分'
    s.append(['用户名', 'QQ号', '测试赛', '障碍赛'])
    s.append(['旧名', qq, 0, -5])
    s.append(['合计', None, 0, -5])
    r = w.create_sheet('赛事资料')
    r.append(['比赛名称', '比赛日期', '年龄范围', '性别限定', '比赛等级', '国家或地区', '场地', '距离（米）', '参赛马匹数'])
    r.append(['测试赛', '2026-01-01', '3岁', '牡牝', 'Jpn1', '日本', '草地', 2000, None])
    r.append(['障碍赛', '2026-01-02', '4+岁', '无', 'J·G1', '日本', '障碍（草地）', 4000, 10])
    out = BytesIO(); w.save(out)
    return out.getvalue()


@pytest.mark.asyncio
async def test_import_filters_and_dedup(db_session):
    db_session.add(User(username='新名', qq='12345', password_hash='x', invite_code='x', is_admin=False))
    await db_session.flush()
    result = await import_workbook(db_session, workbook())
    assert (result['imported_races'], result['imported_scores']) == (2, 2)
    entries = await get_leaderboard(db_session)
    assert [(e.username, e.total_points, e.races_participated, e.avg_points) for e in entries] == [('新名', -5, 2, -2.5)]
    entries = await get_leaderboard(db_session, surface=['障碍'])
    assert (entries[0].total_points, entries[0].races_participated) == (-5, 1)
    entries = await get_leaderboard(db_session, horse_count_max=0)
    assert (entries[0].total_points, entries[0].races_participated) == (0, 1)
    assert len((await import_workbook(db_session, workbook()))['skipped_races']) == 2
    assert len((await db_session.execute(select(HistoricalScore))).scalars().all()) == 2


@pytest.mark.asyncio
async def test_missing_qq_rejects_all(db_session):
    with pytest.raises(HTTPException):
        await import_workbook(db_session, workbook(''))
    assert not (await db_session.execute(select(HistoricalRace))).scalars().all()


@pytest.mark.asyncio
async def test_import_endpoint_requires_admin_and_does_not_create_live_races(async_client):
    denied = await async_client.post('/api/v1/admin/historical-scores', content=workbook())
    assert denied.status_code in (401, 403)
    app.dependency_overrides[get_current_admin] = lambda: object()
    response = await async_client.post('/api/v1/admin/historical-scores', content=workbook())
    assert response.status_code == 200
    assert response.json()['data']['imported_scores'] == 2
    races = await async_client.get('/api/v1/races')
    assert races.json()['data'] == []


@pytest.mark.asyncio
async def test_leaderboard_date_filter_and_matching_races(async_client, db_session):
    await import_workbook(db_session, workbook())
    params = {'date_from': '2026-01-01', 'date_to': '2026-01-01'}
    leaderboard = await async_client.get('/api/v1/leaderboard', params=params)
    assert leaderboard.status_code == 200
    entry = leaderboard.json()['data'][0]
    assert (entry['total_points'], entry['races_participated']) == (0, 1)
    races = await async_client.get('/api/v1/leaderboard/races', params=params)
    assert [(r['name'], r['date'], r['source']) for r in races.json()['data']] == [('测试赛', '2026-01-01', 'historical')]
    obstacle = await async_client.get('/api/v1/leaderboard/races', params={'surface': '障碍'})
    assert [r['name'] for r in obstacle.json()['data']] == ['障碍赛']
    invalid = await async_client.get('/api/v1/leaderboard', params={'date_from': '2026-02-01', 'date_to': '2026-01-01'})
    assert invalid.status_code == 400


