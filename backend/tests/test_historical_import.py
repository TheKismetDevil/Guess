from io import BytesIO
import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from fastapi import HTTPException
from app.models.historical_score import HistoricalImportBatch, HistoricalRace, HistoricalScore
from app.models.user import User
from app.services.historical_import_service import import_workbook, preview_workbook
from app.services import historical_management_service as history
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
    grades = {r.name: r.race_grade for r in (await db_session.execute(select(HistoricalRace))).scalars()}
    assert grades == {'测试赛': 'JPN1', '障碍赛': '其他'}
    # Registered users stay listed with zero participation when no race matches.
    assert [(e.total_points, e.races_participated) for e in await get_leaderboard(db_session, race_grade=['J·G1'])] == [(0, 0)]
    assert [(e.total_points, e.races_participated) for e in await get_leaderboard(db_session, race_grade=['自定义'])] == [(0, 0)]
    assert (await get_leaderboard(db_session, race_grade=['其他']))[0].total_points == -5
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


def changed_workbook(change):
    w = load_workbook(BytesIO(workbook()))
    change(w)
    out = BytesIO()
    w.save(out)
    w.close()
    return out.getvalue()


async def test_preview_is_read_only_and_import_tracks_batch(db_session):
    content = workbook()
    preview = await preview_workbook(db_session, content)
    assert (preview['imported_races'], preview['imported_scores'], preview['participants']) == (2, 2, 1)
    assert not (await db_session.execute(select(HistoricalRace))).scalars().all()
    assert not (await db_session.execute(select(HistoricalImportBatch))).scalars().all()
    result = await import_workbook(db_session, content, '成绩.xlsx', preview['preview_token'])
    batches = await history.list_batches(db_session)
    assert batches[0]['id'] == result['batch_id']
    assert (batches[0]['filename'], batches[0]['race_count'], batches[0]['score_count']) == ('成绩.xlsx', 2, 2)
    repeated = await preview_workbook(db_session, content)
    assert repeated['imported_races'] == 0
    assert all(r['action'] == 'skip' for r in repeated['races'])
    assert (await import_workbook(db_session, content))['batch_id'] is None
    assert len(await history.list_batches(db_session)) == 1


async def test_stale_preview_rejected_without_extra_data(db_session):
    preview = await preview_workbook(db_session, workbook())
    await import_workbook(db_session, workbook())
    with pytest.raises(HTTPException) as exc:
        await import_workbook(db_session, workbook(), preview_token=preview['preview_token'])
    assert exc.value.status_code == 409
    assert len(await history.list_batches(db_session)) == 1


async def test_correct_score_updates_ranking_and_detects_stale_edit(db_session):
    result = await import_workbook(db_session, workbook())
    race = (await history.batch_races(db_session, result['batch_id']))[0]
    score = (await history.race_scores(db_session, race['id']))[0]
    await history.update_score(db_session, score['id'], 10, 0)
    assert (await get_leaderboard(db_session))[0].total_points == 5
    with pytest.raises(HTTPException) as exc:
        await history.update_score(db_session, score['id'], 99, 0)
    assert exc.value.status_code == 409
    assert (await history.race_scores(db_session, race['id']))[0]['points'] == 10


async def test_undo_is_isolated_deletes_batch_and_allows_reimport(db_session):
    first = await import_workbook(db_session, workbook())
    def rename(w):
        w['历史得分']['C1'] = '另一场'
        w['赛事资料']['A2'] = '另一场'
    second = await import_workbook(db_session, changed_workbook(rename))
    db_session.add(User(username='保留用户', qq='99999', password_hash='x', invite_code='keep', is_admin=False))
    await db_session.flush()
    assert await history.undo_batch(db_session, first['batch_id']) == {'removed_races': 2, 'removed_scores': 2, 'restored_races': 0}
    with pytest.raises(HTTPException) as exc:
        await history.undo_batch(db_session, first['batch_id'])
    assert exc.value.status_code == 404
    assert len(await history.batch_races(db_session, second['batch_id'])) == 1
    assert (await db_session.execute(select(User).where(User.qq == '99999'))).scalar_one()
    batches = await history.list_batches(db_session)
    assert [b['id'] for b in batches] == [second['batch_id']]
    assert (await import_workbook(db_session, workbook()))['imported_races'] == 2


async def test_invalid_score_reports_cell_and_does_not_write(db_session):
    content = changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', '错误'))
    with pytest.raises(HTTPException) as exc:
        await preview_workbook(db_session, content)
    assert 'C2' in exc.value.detail['message']
    assert not (await db_session.execute(select(HistoricalRace))).scalars().all()


async def test_blank_middle_race_header_is_rejected(db_session):
    content = changed_workbook(lambda w: setattr(w['历史得分']['C1'], 'value', None))
    with pytest.raises(HTTPException):
        await preview_workbook(db_session, content)


@pytest.mark.parametrize('cell,value', [('H2', 2147483648), ('I2', -1), ('C2', 'x' * 21)])
async def test_bad_metadata_reports_row(db_session, cell, value):
    content = changed_workbook(lambda w: setattr(w['赛事资料'][cell], 'value', value))
    with pytest.raises(HTTPException) as exc:
        await preview_workbook(db_session, content)
    assert '第 2 行' in exc.value.detail['message']


async def test_management_endpoints_require_admin(async_client):
    for method, url in [('post', '/historical-scores/preview'), ('get', '/historical-batches'),
        ('get', '/historical-batches/1/races'), ('post', '/historical-batches/1/undo'),
        ('get', '/historical-races/1/scores'), ('patch', '/historical-scores/1')]:
        response = await async_client.request(method, '/api/v1/admin' + url)
        assert response.status_code in (401, 403)


async def test_admin_preview_edit_and_undo_flow(async_client):
    app.dependency_overrides[get_current_admin] = lambda: object()
    base = '/api/v1/admin'
    preview = (await async_client.post(base + '/historical-scores/preview', content=workbook())).json()['data']
    imported = await async_client.post(base + '/historical-scores', params={'filename': '测试.xlsx', 'preview_token': preview['preview_token']}, content=workbook())
    assert imported.status_code == 200
    batch_id = imported.json()['data']['batch_id']
    race = (await async_client.get(f'{base}/historical-batches/{batch_id}/races')).json()['data'][0]
    score = (await async_client.get(f'{base}/historical-races/{race["id"]}/scores')).json()['data'][0]
    url = f'{base}/historical-scores/{score["id"]}'
    assert (await async_client.patch(url, json={'points': True, 'expected_points': 0})).status_code == 422
    assert (await async_client.patch(url, json={'points': 1.5, 'expected_points': 0})).status_code == 422
    assert (await async_client.patch(url, json={'points': 20, 'expected_points': 0})).status_code == 200
    assert (await async_client.post(f'{base}/historical-batches/{batch_id}/undo')).status_code == 200
    assert (await async_client.get(url.replace('historical-scores', 'historical-races') + '/scores')).status_code == 404


async def reviewed_import(db, content):
    preview = await preview_workbook(db, content)
    decisions = {str(r['race_id']): 'replace' for r in preview['races'] if r['action'] == 'conflict'}
    return await import_workbook(db, content, preview_token=preview['preview_token'], decisions=decisions)


async def test_changed_import_requires_explicit_decision_and_can_keep(db_session):
    original = await import_workbook(db_session, workbook())
    content = changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', 15))
    preview = await preview_workbook(db_session, content)
    assert preview['conflicting_races'] == 1
    item = next(r for r in preview['races'] if r['action'] == 'conflict')
    assert item['differences'] == [{'kind': 'score', 'qq': '12345',
        'before': {'qq': '12345', 'points': 0},
        'after': {'qq': '12345', 'points': 15}}]
    with pytest.raises(HTTPException) as exc:
        await import_workbook(db_session, content, preview_token=preview['preview_token'])
    assert exc.value.detail['code'] == 'DECISIONS_REQUIRED'
    kept = await import_workbook(db_session, content, preview_token=preview['preview_token'], decisions={str(item['race_id']): 'keep'})
    assert kept['batch_id'] is None and kept['updated_races'] == 0
    assert len(await history.list_batches(db_session)) == 1
    assert (await get_leaderboard(db_session))[0].total_points == -5
    assert len(await history.batch_races(db_session, original['batch_id'])) == 2


async def test_replace_diff_metadata_and_score_then_undo_restores_original(db_session):
    original = await import_workbook(db_session, workbook())
    def change(w):
        w['历史得分']['C2'] = 15
        w['赛事资料']['H2'] = 1600
    content = changed_workbook(change)
    preview = await preview_workbook(db_session, content)
    item = next(r for r in preview['races'] if r['action'] == 'conflict')
    assert any(d['kind'] == 'metadata' and d['field'] == 'distance' and d['before'] == 2000 and d['after'] == 1600 for d in item['differences'])
    updated = await reviewed_import(db_session, content)
    assert updated['imported_races'] == 0 and updated['updated_races'] == 1
    assert (await get_leaderboard(db_session))[0].total_points == 10
    assert len(await history.batch_races(db_session, updated['batch_id'])) == 1
    race = await db_session.get(HistoricalRace, item['race_id'])
    assert race.import_batch_id == original['batch_id'] and race.distance == 1600
    result = await history.undo_batch(db_session, updated['batch_id'])
    assert result['restored_races'] == 1 and result['removed_races'] == 0
    assert race.distance == 2000
    assert (await get_leaderboard(db_session))[0].total_points == -5
    with pytest.raises(HTTPException) as exc:
        await history.batch_races(db_session, updated['batch_id'])
    assert exc.value.status_code == 404


async def test_diff_shows_removed_and_added_scores_and_zero_is_not_blank(db_session):
    await import_workbook(db_session, workbook())
    def change(w):
        w['历史得分']['C2'] = None
        w['历史得分'].insert_rows(3)
        w['历史得分'].cell(3, 1, '新用户')
        w['历史得分'].cell(3, 2, '99999')
        w['历史得分'].cell(3, 3, 20)
    content = changed_workbook(change)
    preview = await preview_workbook(db_session, content)
    item = next(r for r in preview['races'] if r['action'] == 'conflict')
    changes = {d['qq']: d for d in item['differences']}
    assert changes['12345']['before']['points'] == 0 and changes['12345']['after'] is None
    assert changes['99999']['before'] is None and changes['99999']['after']['points'] == 20
    await reviewed_import(db_session, content)
    assert [(s['qq'], s['points']) for s in await history.race_scores(db_session, item['race_id'])] == [('99999', 20)]


async def test_partial_decisions_do_not_apply_any_updates(db_session):
    await import_workbook(db_session, workbook())
    def change(w):
        w['历史得分']['C2'] = 1
        w['历史得分']['D2'] = 2
    content = changed_workbook(change)
    preview = await preview_workbook(db_session, content)
    with pytest.raises(HTTPException):
        await import_workbook(db_session, content, preview_token=preview['preview_token'], decisions={str(preview['races'][0]['race_id']): 'replace'})
    assert (await get_leaderboard(db_session))[0].total_points == -5
    assert len(await history.list_batches(db_session)) == 1


async def test_stale_diff_after_manual_edit_cannot_overwrite(db_session):
    original = await import_workbook(db_session, workbook())
    content = changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', 10))
    preview = await preview_workbook(db_session, content)
    race = (await history.batch_races(db_session, original['batch_id']))[0]
    score = (await history.race_scores(db_session, race['id']))[0]
    await history.update_score(db_session, score['id'], 7, 0)
    with pytest.raises(HTTPException) as exc:
        await import_workbook(db_session, content, preview_token=preview['preview_token'], decisions={str(race['id']): 'replace'})
    assert exc.value.status_code == 409
    assert (await history.race_scores(db_session, race['id']))[0]['points'] == 7


async def test_undo_blocks_later_update_and_manual_changes(db_session):
    original = await import_workbook(db_session, workbook())
    first = await reviewed_import(db_session, changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', 10)))
    second = await reviewed_import(db_session, changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', 20)))
    for batch_id in (original['batch_id'], first['batch_id']):
        with pytest.raises(HTTPException) as exc:
            await history.undo_batch(db_session, batch_id)
        assert exc.value.detail['code'] == 'LATER_IMPORT_EXISTS'
    race = (await history.batch_races(db_session, second['batch_id']))[0]
    score = (await history.race_scores(db_session, race['id']))[0]
    await history.update_score(db_session, score['id'], 30, 20)
    with pytest.raises(HTTPException) as exc:
        await history.undo_batch(db_session, second['batch_id'])
    assert exc.value.detail['code'] == 'UNDO_CONFLICT'
    await history.update_score(db_session, score['id'], 20, 30)
    await history.undo_batch(db_session, second['batch_id'])
    await history.undo_batch(db_session, first['batch_id'])
    assert (await get_leaderboard(db_session))[0].total_points == -5


async def test_api_replacement_decisions(async_client):
    import json
    base = '/api/v1/admin/historical-scores'
    app.dependency_overrides[get_current_admin] = lambda: object()
    await async_client.post(base, content=workbook())
    content = changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', 8))
    preview = (await async_client.post(base + '/preview', content=content)).json()['data']
    item = next(r for r in preview['races'] if r['action'] == 'conflict')
    assert (await async_client.post(base, content=content)).status_code == 400
    assert (await async_client.post(base, content=content, params={'decisions': '[]'})).status_code == 400
    result = await async_client.post(base, content=content, params={'preview_token': preview['preview_token'], 'decisions': json.dumps({str(item['race_id']): 'replace'})})
    assert result.status_code == 200 and result.json()['data']['updated_races'] == 1


async def test_default_options_skip_empty_races_but_import_zero_points(db_session):
    content = changed_workbook(lambda w: setattr(w['历史得分']['D2'], 'value', None))
    preview = await preview_workbook(db_session, content)
    assert preview['options'] == {'skip_identical': True, 'skip_empty': True}
    assert [(r['score_count'], r['action']) for r in preview['races']] == [(1, 'import'), (0, 'skip')]
    assert '无成绩' in preview['races'][1]['reason']
    result = await import_workbook(db_session, content, preview_token=preview['preview_token'])
    assert (result['imported_races'], result['imported_scores']) == (1, 1)
    assert (await get_leaderboard(db_session))[0].total_points == 0


@pytest.mark.parametrize('no_participants', [False, True])
async def test_all_empty_does_not_create_batch_unless_option_is_unchecked(db_session, no_participants):
    def clear(w):
        w['历史得分']['C2'] = None
        w['历史得分']['D2'] = None
        if no_participants:
            w['历史得分'].delete_rows(2, 2)
    content = changed_workbook(clear)
    result = await import_workbook(db_session, content)
    assert result['batch_id'] is None and result['imported_races'] == 0
    assert not await history.list_batches(db_session)
    preview = await preview_workbook(db_session, content, skip_empty=False)
    assert preview['imported_races'] == 2 and preview['imported_scores'] == 0
    result = await import_workbook(db_session, content, preview_token=preview['preview_token'], skip_empty=False)
    assert result['imported_races'] == 2
    assert len(await history.batch_races(db_session, result['batch_id'])) == 2


async def test_empty_import_preserves_existing_scores_until_explicitly_enabled_and_reviewed(db_session):
    await import_workbook(db_session, workbook())
    content = changed_workbook(lambda w: setattr(w['历史得分']['C2'], 'value', None))
    preview = await preview_workbook(db_session, content)
    assert preview['conflicting_races'] == 0
    result = await import_workbook(db_session, content, preview_token=preview['preview_token'])
    assert result['batch_id'] is None
    assert (await get_leaderboard(db_session))[0].races_participated == 2
    preview = await preview_workbook(db_session, content, skip_empty=False)
    item = next(r for r in preview['races'] if r['action'] == 'conflict')
    assert item['score_count'] == 0 and item['differences'][0]['after'] is None
    await import_workbook(db_session, content, preview_token=preview['preview_token'],
        decisions={str(item['race_id']): 'replace'}, skip_empty=False)
    assert (await get_leaderboard(db_session))[0].races_participated == 1


async def test_unchecking_skip_identical_reimports_without_duplicate_races(db_session):
    await import_workbook(db_session, workbook())
    preview = await preview_workbook(db_session, workbook(), skip_identical=False)
    assert preview['reimported_races'] == 2 and preview['conflicting_races'] == 0
    assert all(r['action'] == 'reimport' and not r['differences'] for r in preview['races'])
    result = await import_workbook(db_session, workbook(), preview_token=preview['preview_token'], skip_identical=False)
    assert result['updated_races'] == 2 and result['imported_races'] == 0
    assert len((await db_session.execute(select(HistoricalRace))).scalars().all()) == 2
    assert len((await db_session.execute(select(HistoricalScore))).scalars().all()) == 2
    assert (await history.undo_batch(db_session, result['batch_id']))['restored_races'] == 2
    assert (await get_leaderboard(db_session))[0].total_points == -5


async def test_import_options_are_bound_to_preview_token(db_session):
    preview = await preview_workbook(db_session, workbook())
    with pytest.raises(HTTPException) as exc:
        await import_workbook(db_session, workbook(), preview_token=preview['preview_token'], skip_identical=False)
    assert exc.value.status_code == 409
    assert not await history.list_batches(db_session)


async def test_api_import_options_match_preview_and_commit(async_client):
    base = '/api/v1/admin/historical-scores'
    app.dependency_overrides[get_current_admin] = lambda: object()
    content = changed_workbook(lambda w: setattr(w['历史得分']['D2'], 'value', None))
    preview = (await async_client.post(base + '/preview', content=content)).json()['data']
    assert preview['imported_races'] == 1
    preview = (await async_client.post(base + '/preview', content=content,
        params={'skip_empty': 'false', 'skip_identical': 'false'})).json()['data']
    assert preview['imported_races'] == 2
    result = await async_client.post(base, content=content, params={
        'skip_empty': 'false', 'skip_identical': 'false', 'preview_token': preview['preview_token']})
    assert result.status_code == 200 and result.json()['data']['imported_races'] == 2


async def test_grade_normalization_for_steeplechase_and_dropped_grades(db_session):
    w = Workbook()
    s = w.active
    s.title = '历史得分'
    s.append(['用户名', 'QQ号', '三级赛', '地方二级', '障碍自定义', '草地自定义'])
    s.append(['选手', '12345', 3, 1, 5, 10])
    r = w.create_sheet('赛事资料')
    r.append(['比赛名称', '比赛日期', '年龄范围', '性别限定', '比赛等级', '国家或地区', '场地', '距离（米）', '参赛马匹数'])
    r.append(['三级赛', '2026-02-01', '4+岁', '无', 'G3', '日本', '草地', 1800, 12])
    r.append(['地方二级', '2026-02-02', '4+岁', '无', 'Jpn2', '日本', '泥地', 2000, 10])
    r.append(['障碍自定义', '2026-02-03', '4+岁', '无', '自定义', '日本', '障碍', 3900, 9])
    r.append(['草地自定义', '2026-02-04', '3+岁', '无', '自定义', '日本', '草地', 2400, 8])
    out = BytesIO(); w.save(out)
    await import_workbook(db_session, out.getvalue())
    grades = {race.name: race.race_grade for race in (await db_session.execute(select(HistoricalRace))).scalars()}
    assert grades == {'三级赛': '其他', '地方二级': '其他', '障碍自定义': '其他', '草地自定义': '自定义'}
