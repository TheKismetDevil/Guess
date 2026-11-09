"""QQ avatar proxy: opaque keys, shared client pool, deduplication and caching."""
import asyncio
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.endpoints import avatars
from app.core.config import settings
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.user import User
from app.services import avatar_service
from app.services.avatar_service import avatar_key

PNG = b'\x89PNG\r\n\x1a\nfake'


@pytest.fixture(autouse=True)
def fake_download(monkeypatch, db_session):
    calls = []
    sessions = []
    session_factory = async_sessionmaker(db_session.bind)

    def open_session():
        session = session_factory()
        sessions.append(session)
        return session

    async def download(url):
        assert not any(session.in_transaction() for session in sessions)
        calls.append(url)
        await asyncio.sleep(0)
        if 'nk=55555' in url:
            raise httpx.ConnectTimeout('timeout')
        if 'nk=50200' in url:
            return httpx.Response(502, content=b'bad gateway', headers={'content-type': 'text/plain'})
        if 'nk=66666' in url:
            return httpx.Response(200, content=b'<html>', headers={'content-type': 'text/html'})
        return httpx.Response(200, content=PNG, headers={'content-type': 'image/png'})

    avatar_service.clear_cache()
    monkeypatch.setattr(avatars, 'async_session_factory', open_session)
    monkeypatch.setattr(avatar_service, 'download', download)
    yield calls
    avatar_service.clear_cache()


def test_avatar_key_is_stable_opaque_and_hides_qq():
    key = avatar_key('12345')
    assert key == avatar_key('12345') != avatar_key('12346')
    assert key.startswith('v1_') and key != '12345'
    assert avatar_key(None) is None and avatar_key('') is None
    assert settings.avatar_failure_cache_seconds == 60
    assert settings.avatar_cache_seconds == 3 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_avatar_endpoint_serves_and_caches_user_and_history_avatars(async_client, db_session, fake_download):
    db_session.add(User(username='u', qq='12345', password_hash='x', invite_code='A'))
    race = HistoricalRace(name='r', date=date(2026, 1, 1), age_range='3岁', sex_restriction='无',
        race_grade='G1', country='日本', surface='草地', distance=2000, horse_count=10)
    db_session.add(race)
    await db_session.flush()
    db_session.add(HistoricalScore(race_id=race.id, qq='77777', display_name='h', points=1))
    await db_session.commit()
    for qq in ('12345', '77777', '12345'):
        response = await async_client.get(f'/api/v1/avatars/{avatar_key(qq)}')
        assert response.status_code == 200
        assert response.content == PNG
        assert response.headers['content-type'] == 'image/png'
        assert response.headers['cache-control'] == f'public, max-age={settings.avatar_cache_seconds}'
    assert fake_download == ['https://q1.qlogo.cn/g?b=qq&nk=12345&s=100', 'https://q1.qlogo.cn/g?b=qq&nk=77777&s=100']


@pytest.mark.asyncio
async def test_non_image_cached_briefly_but_transient_errors_not_cached(async_client, db_session, fake_download, monkeypatch):
    db_session.add_all([
        User(username='timeout', qq='55555', password_hash='x', invite_code='A'),
        User(username='badgw', qq='50200', password_hash='x', invite_code='B'),
        User(username='html', qq='66666', password_hash='x', invite_code='C'),
    ])
    await db_session.commit()
    key = avatar_key('66666')
    tampered_key = key[:3] + ('A' if key[3] != 'A' else 'B') + key[4:]
    for key in (avatar_key('99999'), 'not-a-key', tampered_key, avatar_key('66666'), avatar_key('66666')):
        response = await async_client.get(f'/api/v1/avatars/{key}')
        assert response.status_code == 404
        assert response.json()['detail']['code'] == 'AVATAR_NOT_FOUND'
    # Non-image upstream response is cached (1 min) instead of hammering upstream.
    assert fake_download.count('https://q1.qlogo.cn/g?b=qq&nk=66666&s=100') == 1

    # Transient errors (timeout / 5xx) are NOT cached and recover immediately on retry.
    for qq in ('55555', '50200'):
        assert (await async_client.get(f'/api/v1/avatars/{avatar_key(qq)}')).status_code == 404

    async def recovered_download(url):
        fake_download.append(url)
        return httpx.Response(200, content=PNG, headers={'content-type': 'image/png'})

    monkeypatch.setattr(avatar_service, 'download', recovered_download)
    for qq in ('55555', '50200'):
        response = await async_client.get(f'/api/v1/avatars/{avatar_key(qq)}')
        assert response.status_code == 200
        assert response.content == PNG


@pytest.mark.asyncio
async def test_concurrent_fetches_for_same_qq_are_deduplicated(monkeypatch):
    gate = asyncio.Event()
    calls = []

    async def slow_download(url):
        calls.append(url)
        await gate.wait()
        return httpx.Response(200, content=PNG, headers={'content-type': 'image/png'})

    monkeypatch.setattr(avatar_service, 'download', slow_download)
    tasks = [asyncio.create_task(avatar_service.fetch_avatar('88888')) for _ in range(5)]
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks)
    assert calls == ['https://q1.qlogo.cn/g?b=qq&nk=88888&s=100']
    assert results == [(PNG, 'image/png')] * 5


@pytest.mark.asyncio
async def test_shared_http_client_reused_and_closed():
    c1 = avatar_service._get_client()
    c2 = avatar_service._get_client()
    assert c1 is c2 and not c1.is_closed
    await avatar_service.close_client()
    assert c1.is_closed
    c3 = avatar_service._get_client()
    assert c3 is not c1 and not c3.is_closed
    await avatar_service.close_client()


@pytest.mark.asyncio
async def test_public_payloads_expose_avatar_key_but_never_qq(async_client, db_session):
    db_session.add(User(username='u', qq='12345', password_hash='x', invite_code='A'))
    await db_session.flush()
    leaderboard = (await async_client.get('/api/v1/leaderboard')).json()['data']
    participants = (await async_client.get('/api/v1/leaderboard/participants')).json()['data']
    assert leaderboard[0]['avatar_key'] == participants[0]['avatar_key'] == avatar_key('12345')
    for payload in (leaderboard, participants):
        assert '12345' not in str(payload)
