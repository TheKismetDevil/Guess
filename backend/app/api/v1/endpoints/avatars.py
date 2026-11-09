"""Avatar API endpoint — proxies QQ avatars by opaque key."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services import avatar_service

router = APIRouter(prefix="/api/v1/avatars", tags=["avatars"])


@router.get("/{key}")
async def get_avatar(key: str, db: AsyncSession = Depends(get_db)):
    """Return the avatar image for an ``avatar_key``. Public endpoint; 404 when unavailable."""
    content, media_type = await avatar_service.get_avatar(db, key)
    return Response(content=content, media_type=media_type,
        headers={"Cache-Control": f"public, max-age={settings.avatar_cache_seconds}"})
