"""One account per QQ, protected placeholder codes, cascading deletes and QQ format."""
from datetime import date

import pytest
from sqlalchemy import select

from app.api.deps import get_current_admin
from app.main import app
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.invite_code import InviteCode
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.services.historical_import_service import import_workbook
from app.services.invite_code_service import create_invite_code, get_invite_codes
from app.utils.qq import is_valid_qq
from tests.test_historical_import import workbook


@pytest.fixture
def admin_client(async_client):
    app.dependency_overrides[get_current_admin] = lambda: {'username': 'admin', 'is_admin': True}
    return async_client


async def placeholder_for(db, qq='12345'):
    return (await db.execute(select(User).where(User.qq == qq))).scalar_one()


@pytest.mark.parametrize('value, valid', [('12345', True), ('1' * 20, True), ('1234', False), ('1' * 21, False),
    ('12345a', False), ('１２３４５', False), (' 12345', False), ('١٢٣٤٥', False)])
def test_qq_must_be_5_to_20_ascii_digits(value, valid):
    assert is_valid_qq(value) is valid


@pytest.mark.asyncio
async def test_qq_format_is_validated_on_register_login_and_invite(admin_client):
    for qq in ('12345a', '１２３４５'):
        register = await admin_client.post('/api/v1/auth/register', json={
            'username': 'someone', 'password': 'secret123', 'qq': qq, 'invite_code': 'ABCDEFGH'})
        login = await admin_client.post('/api/v1/auth/login', json={'qq': qq, 'password': 'secret123'})
        invite = await admin_client.post('/api/v1/admin/invite-codes', json={'qq': qq})
        assert (register.status_code, login.status_code, invite.status_code) == (422, 422, 422)


@pytest.mark.asyncio
async def test_import_rejects_non_digit_qq(db_session):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await import_workbook(db_session, workbook('１２３４５'))
    assert '5-20 位数字' in error.value.detail['message']


@pytest.mark.asyncio
async def test_invite_code_refused_for_registered_qq_or_pending_code(admin_client, db_session):
    db_session.add(User(username='已注册', qq='11111', password_hash='x', invite_code='REG00001'))
    await db_session.flush()
    response = await admin_client.post('/api/v1/admin/invite-codes', json={'qq': '11111'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'QQ_ALREADY_REGISTERED'
    first = await admin_client.post('/api/v1/admin/invite-codes', json={'qq': '22222'})
    assert first.status_code == 201
    second = await admin_client.post('/api/v1/admin/invite-codes', json={'qq': '22222'})
    assert second.status_code == 409
    assert second.json()['detail']['code'] == 'QQ_HAS_UNUSED_CODE'
    assert first.json()['data']['code'] in second.json()['detail']['message']


@pytest.mark.asyncio
async def test_placeholder_qq_reuses_pending_code_and_new_code_attaches_to_placeholder(db_session):
    from fastapi import HTTPException
    await import_workbook(db_session, workbook())
    placeholder = await placeholder_for(db_session)
    with pytest.raises(HTTPException) as error:
        await create_invite_code(db_session, '12345')
    assert error.value.detail['code'] == 'QQ_HAS_UNUSED_CODE'
    # Even if the placeholder's code went missing, a new code is attached to the same placeholder.
    old = (await db_session.execute(select(InviteCode).where(InviteCode.code == placeholder.invite_code))).scalar_one()
    await db_session.delete(old)
    await db_session.flush()
    created = await create_invite_code(db_session, '12345')
    assert created.placeholder_username == placeholder.username
    assert (await placeholder_for(db_session)).invite_code == created.code


@pytest.mark.asyncio
async def test_register_refuses_second_account_for_same_qq(async_client, db_session):
    db_session.add(User(username='已注册', qq='11111', password_hash='x', invite_code='REG00001'))
    db_session.add(InviteCode(code='LEGACY01', status='unused', bound_qq=None))
    await db_session.flush()
    response = await async_client.post('/api/v1/auth/register', json={
        'username': '第二个号', 'password': 'secret123', 'qq': '11111', 'invite_code': 'LEGACY01'})
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'QQ_ALREADY_REGISTERED'
    assert len((await db_session.execute(select(User).where(User.qq == '11111'))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_placeholder_is_listed_searchable_and_cannot_be_deleted(admin_client, db_session):
    await import_workbook(db_session, workbook())
    placeholder = await placeholder_for(db_session)
    listed = (await admin_client.get('/api/v1/admin/invite-codes')).json()['data']
    assert [(c['code'], c['status'], c['placeholder_username'], c['bound_qq']) for c in listed] == [
        (placeholder.invite_code, 'unused', '旧名', '12345')]
    assert [c.code for c in await get_invite_codes(db_session, search='旧名')] == [placeholder.invite_code]
    response = await admin_client.delete(f'/api/v1/admin/invite-codes/{placeholder.invite_code}')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'PLACEHOLDER_PROTECTED'
    assert (await placeholder_for(db_session)).id == placeholder.id
    # After activation the code is an ordinary used code again.
    await admin_client.post('/api/v1/auth/register', json={
        'username': '新名字', 'password': 'secret123', 'qq': '12345', 'invite_code': placeholder.invite_code})
    listed = (await admin_client.get('/api/v1/admin/invite-codes')).json()['data']
    assert [(c['status'], c['bound_username'], c['placeholder_username']) for c in listed] == [('used', '新名字', None)]


@pytest.mark.asyncio
async def test_deleting_used_code_removes_user_votes_and_historical_scores(admin_client, db_session):
    await import_workbook(db_session, workbook())
    placeholder = await placeholder_for(db_session)
    await admin_client.post('/api/v1/auth/register', json={
        'username': '新名字', 'password': 'secret123', 'qq': '12345', 'invite_code': placeholder.invite_code})
    user = await placeholder_for(db_session)
    admin = User(username='admin', qq='10001', password_hash='x', invite_code='ADMIN001', is_admin=True)
    db_session.add(admin)
    await db_session.flush()
    race = Race(name='live', date=date(2026, 2, 1), age_range='其他', sex_restriction='无', race_grade='G1',
        country='日本', distance='1200m', surface='草地', status=RaceStatus.SETTLED, creator_id=admin.id)
    db_session.add(race)
    await db_session.flush()
    horse = RaceHorse(race_id=race.id, horse_id=1, snapshot_data={'name': 'h'}, position=1)
    db_session.add(horse)
    await db_session.flush()
    db_session.add(Vote(user_id=user.id, race_id=race.id, race_horse_id=horse.id, points=10))
    other_race = (await db_session.execute(select(HistoricalRace))).scalars().first()
    db_session.add(HistoricalScore(race_id=other_race.id, qq='99999', display_name='别人', points=7))
    await db_session.flush()

    response = await admin_client.delete(f'/api/v1/admin/invite-codes/{user.invite_code}')
    assert response.status_code == 204
    db_session.expire_all()
    assert (await db_session.execute(select(User).where(User.qq == '12345'))).scalar_one_or_none() is None
    assert (await db_session.execute(select(Vote))).scalars().all() == []
    assert [s.qq for s in (await db_session.execute(select(HistoricalScore))).scalars()] == ['99999']
    assert (await db_session.execute(select(InviteCode))).scalars().all() == []
