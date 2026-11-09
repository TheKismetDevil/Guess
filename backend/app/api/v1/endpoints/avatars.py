"""Avatar API endpoint — proxies QQ avatars by opaque key."""

from fastapi import APIRouter, Response

from app.core.config import settings
from app.core.database import async_session_factory
from app.services import avatar_service

router = APIRouter(prefix="/api/v1/avatars", tags=["avatars"])


@router.get("/{key}")
async def get_avatar(key: str):
    """Return the avatar image for an ``avatar_key``. Public endpoint; 404 when unavailable."""
    async with async_session_factory() as db:
        qq = await avatar_service.resolve_qq(db, key)
    content, media_type = await avatar_service.get_avatar(qq)
    return Response(content=content, media_type=media_type,
        headers={"Cache-Control": f"public, max-age={settings.avatar_cache_seconds}"})
