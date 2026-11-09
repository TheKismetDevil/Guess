"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, avatars, horses, leaderboard, races, results, votes

router = APIRouter()
router.include_router(admin.router)
router.include_router(auth.router)
router.include_router(avatars.router)
router.include_router(horses.router)
router.include_router(leaderboard.router)
router.include_router(races.router)
router.include_router(results.router)
router.include_router(votes.router)
