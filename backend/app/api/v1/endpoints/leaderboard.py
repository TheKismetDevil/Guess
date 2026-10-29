"""Leaderboard API endpoint — public ranking data."""

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import leaderboard_service
from app.api.deps import get_optional_user

router = APIRouter(prefix="/api/v1", tags=["leaderboard"])


def leaderboard_filters(
    age_range: list[str] | None = Query(None, description="年龄范围筛选（多选）"),
    sex_restriction: list[str] | None = Query(None, description="性别限定筛选（多选）"),
    race_grade: list[str] | None = Query(None, description="比赛等级筛选（多选）"),
    country: list[str] | None = Query(None, description="国家或地区筛选（多选）"),
    surface: list[str] | None = Query(None, description="场地筛选（多选）"),
    distance_min: int | None = Query(None, description="最小长度（米）"),
    distance_max: int | None = Query(None, description="最大长度（米）"),
    horse_count_min: int | None = Query(None, description="最少参赛马匹数"),
    horse_count_max: int | None = Query(None, description="最多参赛马匹数"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail={'code': 'INVALID_DATE_RANGE', 'message': '开始日期不能晚于结束日期'})
    return dict(age_range=age_range, sex_restriction=sex_restriction, race_grade=race_grade, country=country, surface=surface, distance_min=distance_min, distance_max=distance_max, horse_count_min=horse_count_min, horse_count_max=horse_count_max, date_from=date_from, date_to=date_to)


@router.get("/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db), filters: dict = Depends(leaderboard_filters)):
    """Get the global leaderboard sorted by cumulative points descending.

    Supports optional filtering by race tags (age_range, race_grade, etc.)
    and numeric ranges (distance, horse_count). Tag filters support multi-select.

    Public endpoint — no authentication required.
    Returns all users including those with zero settled races.
    """
    entries = await leaderboard_service.get_leaderboard(db, **filters)
    return {"data": [e.model_dump() for e in entries]}


@router.get('/leaderboard/races')
async def get_leaderboard_races(db: AsyncSession = Depends(get_db), filters: dict = Depends(leaderboard_filters), current_user=Depends(get_optional_user)):
    return {'data': await leaderboard_service.get_matching_races(db, include_hidden=bool(current_user and current_user.is_admin), **filters)}
