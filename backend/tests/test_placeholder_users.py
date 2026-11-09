"""Placeholder users created for historical QQs and activated on registration."""
import pytest
from sqlalchemy import select

from app.models.historical_score import HistoricalScore
from app.models.user import User
from app.services import historical_management_service as history
from app.services.head_to_head_service import get_participants
from app.services.historical_import_service import import_workbook
from app.services.invite_code_service import get_invite_codes
from app.services.leaderboard_service import get_leaderboard
from app.services.placeholder_user_service import is_placeholder
from tests.test_historical_import import workbook


async def users_by_qq(db, qq):
    return (await db.execute(select(User).where(User.qq == qq))).scalars().all()


@pytest.mark.asyncio
async def test_import_creates_placeholder_user_with_unused_invite_code(db_session):
    result = await import_workbook(db_session, workbook())
    assert result['placeholder_users'] == 1
    [user] = await users_by_qq(db_session, '12345')
    assert is_placeholder(user) and user.username == '旧名' and not user.is_admin
    [code] = await get_invite_codes(db_session)
    assert (code.code, code.status, code.bound_qq, code.bound_username, code.placeholder_username) == (
        user.invite_code, 'unused', '12345', None, '旧名'
    )
    # Leaderboard and head-to-head treat the placeholder as a normal user.
    assert [(e.username, e.total_points) for e in await get_leaderboard(db_session)] == [('旧名', -5)]
    assert [(p['username'], p['kind']) for p in await get_participants(db_session)] == [('旧名', 'user')]
    # Re-importing does not create duplicates.
    await import_workbook(db_session, workbook())
    assert len(await users_by_qq(db_session, '12345')) == 1


@pytest.mark.asyncio
async def test_existing_account_is_not_duplicated(db_session):
    db_session.add(User(username='已注册', qq='12345', password_hash='x', invite_code='REG00001'))
    await db_session.flush()
    result = await import_workbook(db_session, workbook())
    assert result['placeholder_users'] == 0
    assert [u.username for u in await users_by_qq(db_session, '12345')] == ['已注册']
    [code] = await get_invite_codes(db_session)
    assert (code.code, code.status, code.bound_username) == ('REG00001', 'used', '已注册')


@pytest.mark.asyncio
async def test_placeholder_reuses_pending_invite_code_and_avoids_username_clash(db_session):
    db_session.add(User(username='旧名', qq='99999', password_hash='x', invite_code='OTHER001'))
    db_session.add(User(username=None, password_hash=None, qq='12345', invite_code='PEND0001'))
    await db_session.flush()
    await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    assert (user.username, user.invite_code) == ('旧名#2', 'PEND0001')
    assert len(await get_invite_codes(db_session)) == 2


@pytest.mark.asyncio
async def test_undo_removes_orphan_placeholder_but_keeps_invite_code(db_session):
    result = await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    code = user.invite_code
    await history.undo_batch(db_session, result['batch_id'])
    [pending] = await users_by_qq(db_session, '12345')
    assert pending.username is None and pending.password_hash is None and pending.invite_code == code
    assert [(c.code, c.status, c.placeholder_username) for c in await get_invite_codes(db_session)] == [
        (code, 'unused', None)
    ]
    assert await get_leaderboard(db_session) == []
    # A new import reuses the kept code.
    await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    assert user.username == '旧名' and user.invite_code == code


@pytest.mark.asyncio
async def test_registration_activates_placeholder_and_keeps_history(async_client, db_session):
    imported = await import_workbook(db_session, workbook())
    [placeholder] = await users_by_qq(db_session, '12345')
    # Placeholders cannot log in before activation.
    response = await async_client.post('/api/v1/auth/login', json={'qq': '12345', 'password': 'whatever'})
    assert response.status_code == 401
    response = await async_client.post('/api/v1/auth/register', json={
        'username': '新名字', 'password': 'secret123', 'qq': '12345', 'invite_code': placeholder.invite_code})
    assert response.status_code == 201, response.text
    body = response.json()['data']
    assert body['user']['id'] == placeholder.id
    assert body['user']['username'] == '新名字'
    assert body['user']['avatar_key']
    [user] = await users_by_qq(db_session, '12345')
    assert not is_placeholder(user)
    [code] = await get_invite_codes(db_session)
    assert (code.code, code.status, code.bound_username, code.placeholder_username) == (
        user.invite_code, 'used', '新名字', None
    )
    assert [(e.username, e.total_points) for e in await get_leaderboard(db_session)] == [('新名字', -5)]
    assert len((await db_session.execute(select(HistoricalScore))).scalars().all()) == 2
    response = await async_client.post('/api/v1/auth/login', json={'username': '新名字', 'password': 'secret123'})
    assert response.status_code == 200
    # Activated users are no longer removed when their history disappears.
    await history.undo_batch(db_session, imported['batch_id'])
    assert [u.username for u in await users_by_qq(db_session, '12345')] == ['新名字']


@pytest.mark.asyncio
async def test_registration_rejects_name_of_another_user(async_client, db_session):
    db_session.add(User(username='占用者', qq='99999', password_hash='x', invite_code='OTHER001'))
    await db_session.flush()
    await import_workbook(db_session, workbook())
    [placeholder] = await users_by_qq(db_session, '12345')
    response = await async_client.post('/api/v1/auth/register', json={
        'username': '占用者', 'password': 'secret123', 'qq': '12345', 'invite_code': placeholder.invite_code})
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'USERNAME_EXISTS'
