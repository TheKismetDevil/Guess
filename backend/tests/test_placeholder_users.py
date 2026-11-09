"""Placeholder users created for historical QQs and activated on registration."""
import pytest
from sqlalchemy import select

from app.models.historical_score import HistoricalScore
from app.models.invite_code import InviteCode
from app.models.user import User
from app.services import historical_management_service as history
from app.services.head_to_head_service import get_participants
from app.services.historical_import_service import import_workbook
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
    code = (await db_session.execute(select(InviteCode).where(InviteCode.code == user.invite_code))).scalar_one()
    assert (code.status, code.bound_qq, code.bound_username) == ('unused', '12345', None)
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
    assert (await db_session.execute(select(InviteCode))).scalars().all() == []


@pytest.mark.asyncio
async def test_placeholder_reuses_pending_invite_code_and_avoids_username_clash(db_session):
    db_session.add(User(username='旧名', qq='99999', password_hash='x', invite_code='OTHER001'))
    db_session.add(InviteCode(code='PEND0001', status='unused', bound_qq='12345'))
    await db_session.flush()
    await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    assert (user.username, user.invite_code) == ('旧名#2', 'PEND0001')
    assert len((await db_session.execute(select(InviteCode))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_undo_removes_orphan_placeholder_but_keeps_invite_code(db_session):
    result = await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    code = user.invite_code
    await history.undo_batch(db_session, result['batch_id'])
    assert await users_by_qq(db_session, '12345') == []
    assert (await db_session.execute(select(InviteCode).where(InviteCode.code == code))).scalar_one().status == 'unused'
    # A new import reuses the kept code.
    await import_workbook(db_session, workbook())
    [user] = await users_by_qq(db_session, '12345')
    assert user.invite_code == code


@pytest.mark.asyncio
async def test_registration_activates_placeholder_and_keeps_history(async_client, db_session):
    await import_workbook(db_session, workbook())
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
    code = (await db_session.execute(select(InviteCode).where(InviteCode.code == user.invite_code))).scalar_one()
    assert (code.status, code.bound_username) == ('used', '新名字')
    assert [(e.username, e.total_points) for e in await get_leaderboard(db_session)] == [('新名字', -5)]
    assert len((await db_session.execute(select(HistoricalScore))).scalars().all()) == 2
    response = await async_client.post('/api/v1/auth/login', json={'username': '新名字', 'password': 'secret123'})
    assert response.status_code == 200
    # Activated users are no longer removed when their history disappears.
    await history.undo_batch(db_session, 1)
    assert len(await users_by_qq(db_session, '12345')) == 1


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
