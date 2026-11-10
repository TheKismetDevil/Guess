"""Leaderboard service — aggregated user rankings with tag filters.

Queries live Vote.points and historical HistoricalScore.points directly by
User.id to compute cumulative scores, race counts, and per-race averages.
"""

from datetime import date
from fractions import Fraction
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.schemas.leaderboard import LeaderboardEntry
from app.services.avatar_service import avatar_key


async def get_leaderboard(
    db: AsyncSession,
    age_range: list[str] | None = None,
    sex_restriction: list[str] | None = None,
    race_grade: list[str] | None = None,
    country: list[str] | None = None,
    surface: list[str] | None = None,
    distance_min: int | None = None,
    distance_max: int | None = None,
    horse_count_min: int | None = None,
    horse_count_max: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: Literal["total_points", "avg_points"] = "total_points",
) -> list[LeaderboardEntry]:
    """Return all active/placeholder non-admin users sorted by total or average points."""
    filters = dict(
        age_range=age_range,
        sex_restriction=sex_restriction,
        race_grade=race_grade,
        country=country,
        surface=surface,
        distance_min=distance_min,
        distance_max=distance_max,
        horse_count_min=horse_count_min,
        horse_count_max=horse_count_max,
        date_from=date_from,
        date_to=date_to,
    )
    has_filters = any(
        v is not None and v != []
        for v in filters.values()
    )

    vote_query = (
        select(
            Vote.user_id,
            func.sum(Vote.points).label("points"),
            func.count(func.distinct(Vote.race_id)).label("races"),
        )
        .join(Race, Vote.race_id == Race.id)
        .where(
            Vote.points.isnot(None),
            Race.status == RaceStatus.SETTLED,
            Race.is_hidden == False,
        )
    )
    if has_filters:
        vote_query = filter_race_query(vote_query, Race, filters)
    vote_query = vote_query.group_by(Vote.user_id)

    if has_filters:
        history_query = (
            select(
                HistoricalScore.user_id,
                func.sum(HistoricalScore.points).label("points"),
                func.count(HistoricalScore.id).label("races"),
            )
            .join(HistoricalRace, HistoricalScore.race_id == HistoricalRace.id)
        )
        history_query = filter_race_query(
            history_query, HistoricalRace, filters
        ).group_by(HistoricalScore.user_id)
    else:
        history_query = select(
            HistoricalScore.user_id,
            func.sum(HistoricalScore.points).label("points"),
            func.count(HistoricalScore.id).label("races"),
        ).group_by(HistoricalScore.user_id)

    users = (
        await db.execute(
            select(User.id, User.username, User.qq).where(
                User.is_admin == False,
                User.username.isnot(None),
            )
        )
    ).all()

    live_by_user = {
        uid: (int(pts or 0), int(cnt or 0))
        for uid, pts, cnt in (await db.execute(vote_query)).all()
    }
    hist_by_user = {
        uid: (int(pts or 0), int(cnt or 0))
        for uid, pts, cnt in (await db.execute(history_query)).all()
    }

    entries: list[LeaderboardEntry] = []
    for uid, username, qq in users:
        l_pts, l_cnt = live_by_user.get(uid, (0, 0))
        h_pts, h_cnt = hist_by_user.get(uid, (0, 0))
        total_pts = l_pts + h_pts
        total_cnt = l_cnt + h_cnt
        entries.append(
            LeaderboardEntry(
                username=username,
                total_points=total_pts,
                races_participated=total_cnt,
                avg_points=round(total_pts / total_cnt, 3) if total_cnt else 0.0,
                avatar_key=avatar_key(qq),
            )
        )

    if sort_by == "avg_points":
        matching_races = await get_matching_races(db, **filters)
        # ceil(N * 60%) using integers; the denominator matches the displayed race list.
        minimum_races = (len(matching_races) * 3 + 4) // 5
        entries = [
            entry for entry in entries if entry.races_participated >= minimum_races
        ]

    def ranking_key(entry: LeaderboardEntry):
        average = (
            Fraction(entry.total_points, entry.races_participated)
            if entry.races_participated
            else Fraction(0)
        )
        return (
            (average, entry.total_points)
            if sort_by == "avg_points"
            else (entry.total_points, average)
        )

    return sorted(entries, key=ranking_key, reverse=True)


def filter_race_query(query, model, filters):
    """Apply the same race conditions to race lists, leaderboard, and head-to-head."""
    for key in ("age_range", "sex_restriction", "race_grade", "country", "surface"):
        if filters.get(key):
            query = query.where(getattr(model, key).in_(filters[key]))
    for key, is_min in (("date_from", True), ("date_to", False)):
        if filters.get(key) is not None:
            query = query.where(
                model.date >= filters[key] if is_min else model.date <= filters[key]
            )
    distance = model.distance
    count = (
        select(func.count(RaceHorse.id))
        .where(RaceHorse.race_id == Race.id)
        .correlate(Race)
        .scalar_subquery()
        if model is Race
        else HistoricalRace.horse_count
    )
    for key, column, is_min in (
        ("distance_min", distance, True),
        ("distance_max", distance, False),
        ("horse_count_min", count, True),
        ("horse_count_max", count, False),
    ):
        if filters.get(key) is not None:
            query = query.where(
                column >= filters[key] if is_min else column <= filters[key]
            )
    return query


async def get_matching_races(
    db: AsyncSession, **filters
) -> list[dict]:
    """List public races with scores using the same inclusive conditions as the ranking."""
    live = select(Race).where(
        Race.status == RaceStatus.SETTLED,
        Race.is_hidden == False,
        select(Vote.id)
        .join(User, User.id == Vote.user_id)
        .where(Vote.race_id == Race.id, Vote.points.isnot(None), User.is_admin == False)
        .exists(),
    )
    historical = select(HistoricalRace).where(
        select(HistoricalScore.id)
        .join(User, User.id == HistoricalScore.user_id)
        .where(
            HistoricalScore.race_id == HistoricalRace.id,
            User.is_admin == False,
        )
        .exists()
    )
    live = filter_race_query(live, Race, filters)
    historical = filter_race_query(historical, HistoricalRace, filters)
    live_races = (await db.execute(live)).scalars().all()
    historical_races = (await db.execute(historical)).scalars().all()
    items = [
        {
            "id": r.id,
            "name": r.name,
            "date": r.date.isoformat(),
            "source": "live",
        }
        for r in live_races
    ]
    items += [
        {"id": None, "name": r.name, "date": r.date.isoformat(), "source": "historical"}
        for r in historical_races
    ]
    return sorted(items, key=lambda item: (item["date"], item["name"]), reverse=True)
