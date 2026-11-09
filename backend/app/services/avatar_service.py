"""QQ avatar proxy.

Browsers only ever see an opaque ``avatar_key``; the server resolves it back to
a QQ number, downloads the avatar from the QQ avatar service using a shared
connection pool, deduplicates concurrent fetches for the same QQ, and caches
the image so raw QQ numbers are never exposed in public pages or image URLs.
"""
import asyncio
import hmac
import re
import time

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.security import opaque_key
from app.models.historical_score import HistoricalScore
from app.models.user import User

AVATAR_KIND = 'avatar'
MAX_AVATAR_BYTES = 512 * 1024
MAX_CACHE_ENTRIES = 2000
_KEY_PATTERN = re.compile(r'^[0-9a-f]{64}$')

# qq -> (expires_at, content, media_type); content None caches a non-transient failure.
_cache: dict[str, tuple[float, bytes | None, str | None]] = {}
_inflight: dict[str, asyncio.Task[tuple[bytes, str] | None]] = {}
_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def avatar_key(qq: str | None) -> str | None:
    """Public, non-reversible key for a QQ avatar (None when there is no QQ)."""
    if not qq:
        return None
    return opaque_key(AVATAR_KIND, qq).split(':', 1)[1]


def clear_cache() -> None:
    _cache.clear()


def _get_client() -> httpx.AsyncClient:
    """Return a shared ``httpx.AsyncClient`` bound to the current event loop."""
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client.is_closed or _client_loop is not loop:
        _client = httpx.AsyncClient(
            timeout=settings.avatar_fetch_timeout_seconds,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        _client_loop = loop
    return _client


async def close_client() -> None:
    """Close the shared HTTP client on application shutdown."""
    global _client, _client_loop
    client, _client, _client_loop = _client, None, None
    if client is not None and not client.is_closed:
        await client.aclose()


async def resolve_qq(db, key: str) -> str | None:
    if not _KEY_PATTERN.match(key):
        return None
    qqs = (await db.execute(select(User.qq).union(select(HistoricalScore.qq)))).scalars().all()
    for qq in qqs:
        if hmac.compare_digest(avatar_key(qq), key):
            return qq
    return None


async def download(url: str) -> httpx.Response:
    return await _get_client().get(url)


async def _fetch_and_cache(qq: str) -> tuple[bytes, str] | None:
    try:
        result = None
        should_cache = True
        try:
            response = await download(settings.qq_avatar_url.format(qq=qq))
            media_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
            if response.status_code == 200 and media_type.startswith('image/') and 0 < len(response.content) <= MAX_AVATAR_BYTES:
                result = (response.content, media_type)
            elif response.status_code >= 500:
                should_cache = False
        except httpx.HTTPError:
            # Transient timeout / connection error: don't cache so retries recover immediately.
            result = None
            should_cache = False

        if should_cache:
            ttl = settings.avatar_cache_seconds if result else settings.avatar_failure_cache_seconds
            if len(_cache) >= MAX_CACHE_ENTRIES:
                _cache.clear()
            _cache[qq] = (time.monotonic() + ttl, *(result or (None, None)))
        else:
            _cache.pop(qq, None)
        return result
    finally:
        _inflight.pop(qq, None)


async def fetch_avatar(qq: str) -> tuple[bytes, str] | None:
    """Download (or reuse the cached / in-flight) avatar image for a QQ number."""
    if not qq.isdigit():
        return None
    now = time.monotonic()
    cached = _cache.get(qq)
    if cached and cached[0] > now:
        return (cached[1], cached[2]) if cached[1] is not None else None
    task = _inflight.get(qq)
    if task is None:
        task = asyncio.create_task(_fetch_and_cache(qq))
        _inflight[qq] = task
    return await asyncio.shield(task)


async def get_avatar(db, key: str) -> tuple[bytes, str]:
    qq = await resolve_qq(db, key)
    image = await fetch_avatar(qq) if qq else None
    if image is None:
        raise HTTPException(status_code=404, detail={'code': 'AVATAR_NOT_FOUND', 'message': '头像不存在或暂时无法获取'})
    return image
