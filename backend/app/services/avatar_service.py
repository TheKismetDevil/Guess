"""QQ avatar proxy.

Browsers only ever see an opaque ``avatar_key``; the server resolves it back to
a QQ number, downloads the avatar from the QQ avatar service and caches it, so
raw QQ numbers are never exposed in public pages or image URLs.
"""
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

# qq -> (expires_at, content, media_type); content None caches a failed download.
_cache: dict[str, tuple[float, bytes | None, str | None]] = {}


def avatar_key(qq: str | None) -> str | None:
    """Public, non-reversible key for a QQ avatar (None when there is no QQ)."""
    if not qq:
        return None
    return opaque_key(AVATAR_KIND, qq).split(':', 1)[1]


def clear_cache() -> None:
    _cache.clear()


async def resolve_qq(db, key: str) -> str | None:
    if not _KEY_PATTERN.match(key):
        return None
    qqs = (await db.execute(select(User.qq).union(select(HistoricalScore.qq)))).scalars().all()
    for qq in qqs:
        if hmac.compare_digest(avatar_key(qq), key):
            return qq
    return None


async def download(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=settings.avatar_fetch_timeout_seconds, follow_redirects=True) as client:
        return await client.get(url)


async def fetch_avatar(qq: str) -> tuple[bytes, str] | None:
    """Download (or reuse the cached) avatar image for a QQ number."""
    if not qq.isdigit():
        return None
    now = time.monotonic()
    cached = _cache.get(qq)
    if cached and cached[0] > now:
        return (cached[1], cached[2]) if cached[1] is not None else None
    result = None
    try:
        response = await download(settings.qq_avatar_url.format(qq=qq))
        media_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
        if response.status_code == 200 and media_type.startswith('image/') and 0 < len(response.content) <= MAX_AVATAR_BYTES:
            result = (response.content, media_type)
    except httpx.HTTPError:
        result = None
    ttl = settings.avatar_cache_seconds if result else settings.avatar_failure_cache_seconds
    if len(_cache) >= MAX_CACHE_ENTRIES:
        _cache.clear()
    _cache[qq] = (now + ttl, *(result or (None, None)))
    return result


async def get_avatar(db, key: str) -> tuple[bytes, str]:
    qq = await resolve_qq(db, key)
    image = await fetch_avatar(qq) if qq else None
    if image is None:
        raise HTTPException(status_code=404, detail={'code': 'AVATAR_NOT_FOUND', 'message': '头像不存在或暂时无法获取'})
    return image
