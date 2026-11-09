"""QQ avatar proxy: opaque keys, server-side download and caching."""
from datetime import date

import httpx
import pytest

from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.user import User
from app.services import avatar_service
from app.services.avatar_service import avatar_key

PNG = b'\x89PNG\r\n\x1a\nfake'


@pytest.fixture(autouse=True)
def fake_download(monkeypatch):
    calls = []

    async def download(url):
        calls.append(url)
        if 'nk=55555' in url:
            raise httpx.ConnectTimeout('timeout')
        if 'nk=66666' in url:
            return httpx.Response(200, content=b'<html>', headers={'content-type': 'text/html'})
        return httpx.Response(200, content=PNG, headers={'content-type': 'image/png'})

    avatar_service.clear_cache()
    monkeypatch.setattr(avatar_service, 'download', download)
    yield calls
    avatar_service.clear_cache()


def test_avatar_key_is_stable_opaque_and_hides_qq():
    key = avatar_key('12345')
    assert key == avatar_key('12345') != avatar_key('12346')
    assert len(key) == 64 and '12345' not in key
    assert avatar_key(None) is None and avatar_key('') is None


@pytest.mark.asyncio
async def test_avatar_endpoint_serves_and_caches_user_and_history_avatars(async_client, db_session, fake_download):
    db_session.add(User(username='u', qq='12345', password_hash='x', invite_code='A'))
    race = HistoricalRace(name='r', date=date(2026, 1, 1), age_range='3岁', sex_restriction='无',
        race_grade='G1', country='日本', surface='草地', distance=2000, horse_count=10)
    db_session.add(race)
    await db_session.flush()
    db_session.add(HistoricalScore(race_id=race.id, qq='77777', display_name='h', points=1))
    await db_session.flush()
    for qq in ('12345', '77777', '12345'):
        response = await async_client.get(f'/api/v1/avatars/{avatar_key(qq)}')
        assert response.status_code == 200
        assert response.content == PNG
        assert response.headers['content-type'] == 'image/png'
        assert 'max-age' in response.headers['cache-control']
    assert fake_download == ['https://q1.qlogo.cn/g?b=qq&nk=12345&s=100', 'https://q1.qlogo.cn/g?b=qq&nk=77777&s=100']


@pytest.mark.asyncio
async def test_unknown_malformed_or_failed_avatars_return_404(async_client, db_session, fake_download):
    db_session.add_all([User(username='timeout', qq='55555', password_hash='x', invite_code='A'),
        User(username='html', qq='66666', password_hash='x', invite_code='B')])
    await db_session.flush()
    for key in (avatar_key('99999'), 'not-a-key', avatar_key('55555'), avatar_key('66666'), avatar_key('55555')):
        response = await async_client.get(f'/api/v1/avatars/{key}')
        assert response.status_code == 404
        assert response.json()['detail']['code'] == 'AVATAR_NOT_FOUND'
    # Failures are cached briefly instead of hammering the upstream service.
    assert fake_download.count('https://q1.qlogo.cn/g?b=qq&nk=55555&s=100') == 1


@pytest.mark.asyncio
async def test_public_payloads_expose_avatar_key_but_never_qq(async_client, db_session):
    db_session.add(User(username='u', qq='12345', password_hash='x', invite_code='A'))
    await db_session.flush()
    leaderboard = (await async_client.get('/api/v1/leaderboard')).json()['data']
    participants = (await async_client.get('/api/v1/leaderboard/participants')).json()['data']
    assert leaderboard[0]['avatar_key'] == participants[0]['avatar_key'] == avatar_key('12345')
    for payload in (leaderboard, participants):
        assert '12345' not in str(payload)
