"""Leaderboard service — aggregated user rankings with tag filters.

Queries Vote.points (directly on the Vote model) to compute
cumulative scores, race counts, and per-race averages.
Supports filtering by race tags, horse count, and distance range.
"""

import sqlalchemy as sa
from datetime import date
from sqlalchemy import Numeric, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Subquery

from app.models.user import User
from app.models.vote import Vote
from app.models.race import Race, RaceHorse
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.schemas.leaderboard import LeaderboardEntry


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
) -> list[LeaderboardEntry]:
    """Return all users sorted by cumulative points descending.

    Supports filtering by race tags and numeric ranges.
    Filters apply only to settled races with points — users who have
    no qualifying races still appear with 0 values.
    """

    has_filters = any([
        age_range, sex_restriction, race_grade, country, surface,
        distance_min is not None, distance_max is not None,
        horse_count_min is not None, horse_count_max is not None,
        date_from is not None, date_to is not None,
    ])

    if has_filters:
        # Build filtered votes subquery: Vote INNER JOIN Race WHERE race_filters
        vote_subq_base = (
            select(Vote.user_id, Vote.points, Vote.race_id)
            .select_from(Vote)
            .join(Race, Vote.race_id == Race.id)
            .where(Vote.points.isnot(None))
        )
        if date_from is not None:
            vote_subq_base = vote_subq_base.where(Race.date >= date_from)
        if date_to is not None:
            vote_subq_base = vote_subq_base.where(Race.date <= date_to)

        # Race tag filters
        if age_range:
            vote_subq_base = vote_subq_base.where(Race.age_range.in_(age_range))
        if sex_restriction:
            vote_subq_base = vote_subq_base.where(Race.sex_restriction.in_(sex_restriction))
        if race_grade:
            vote_subq_base = vote_subq_base.where(Race.race_grade.in_(race_grade))
        if country:
            vote_subq_base = vote_subq_base.where(Race.country.in_(country))
        if surface:
            vote_subq_base = vote_subq_base.where(Race.surface.in_(surface))

        # Distance filter: parse numeric part from distance string
        if distance_min is not None or distance_max is not None:
            distance_expr = func.cast(
                func.regexp_replace(Race.distance, '[^0-9]', '', 'g'),
                sa.Integer,
            )
            if distance_min is not None:
                vote_subq_base = vote_subq_base.where(distance_expr >= distance_min)
            if distance_max is not None:
                vote_subq_base = vote_subq_base.where(distance_expr <= distance_max)

        # Horse count filter: count race_horses per race using a scalar subquery
        if horse_count_min is not None or horse_count_max is not None:
            horse_count_subq = (
                select(func.count(RaceHorse.id))
                .where(RaceHorse.race_id == Race.id)
                .correlate(Race)
                .scalar_subquery()
            )
            if horse_count_min is not None:
                vote_subq_base = vote_subq_base.where(horse_count_subq >= horse_count_min)
            if horse_count_max is not None:
                vote_subq_base = vote_subq_base.where(horse_count_subq <= horse_count_max)

        filtered_votes: Subquery = vote_subq_base.subquery()
    else:
        # No filters: simple subquery of all votes with points
        filtered_votes: Subquery = (
            select(Vote.user_id, Vote.points, Vote.race_id)
            .select_from(Vote)
            .where(Vote.points.isnot(None))
            .subquery()
        )

    total_points_col = func.coalesce(func.sum(filtered_votes.c.points), 0)
    races_col = func.count(func.distinct(filtered_votes.c.race_id))
    sum_points = func.coalesce(func.sum(filtered_votes.c.points), 0.0)
    divisor = func.nullif(func.count(func.distinct(filtered_votes.c.race_id)), 0)
    avg_points_col = func.round(
        sa.cast(sum_points / divisor, Numeric),
        1,
    )

    query = (
        select(
            User.username,
            User.qq,
            total_points_col.label("total_points"),
            races_col.label("races_participated"),
            avg_points_col.label("avg_points"),
        )
        .outerjoin(
            filtered_votes,
            User.id == filtered_votes.c.user_id,
        )
        .group_by(User.id, User.username, User.qq)
        .where(User.is_admin == False)
        .order_by(
            total_points_col.desc(),
            avg_points_col.desc(),
        )
    )

    result = await db.execute(query)
    rows = result.all()

    history_query = select(HistoricalScore.qq, func.max(HistoricalScore.display_name), func.sum(HistoricalScore.points), func.count(HistoricalScore.id)).join(HistoricalRace, HistoricalScore.race_id == HistoricalRace.id)
    if date_from is not None:
        history_query = history_query.where(HistoricalRace.date >= date_from)
    if date_to is not None:
        history_query = history_query.where(HistoricalRace.date <= date_to)
    for values, column in [(age_range, HistoricalRace.age_range), (sex_restriction, HistoricalRace.sex_restriction), (race_grade, HistoricalRace.race_grade), (country, HistoricalRace.country), (surface, HistoricalRace.surface)]:
        if values:
            history_query = history_query.where(column.in_(values))
    for value, column, is_min in [(distance_min, HistoricalRace.distance, True), (distance_max, HistoricalRace.distance, False), (horse_count_min, HistoricalRace.horse_count, True), (horse_count_max, HistoricalRace.horse_count, False)]:
        if value is not None:
            history_query = history_query.where(column >= value if is_min else column <= value)
    history_query = history_query.group_by(HistoricalScore.qq)
    admin_qqs = set((await db.execute(select(User.qq).where(User.is_admin == True))).scalars())
    totals = [[row.username, int(row.total_points or 0), int(row.races_participated or 0)] for row in rows]
    by_qq = {}
    for row, entry in zip(rows, totals):
        by_qq.setdefault(row.qq, []).append(entry)
    for qq, name, points, count in (await db.execute(history_query)).all():
        if qq in admin_qqs:
            continue
        matches = by_qq.get(qq, [])
        if len(matches) == 1:
            entry = matches[0]
        else:
            entry = [name, 0, 0]
            totals.append(entry)
        entry[1] += int(points)
        entry[2] += count
    entries = [LeaderboardEntry(username=name, total_points=points, races_participated=count, avg_points=round(points / count, 1) if count else 0.0) for name, points, count in totals]
    return sorted(entries, key=lambda entry: (entry.total_points, entry.avg_points), reverse=True)


async def get_matching_races(db: AsyncSession, include_hidden: bool = False, **filters) -> list[dict]:
    """List races with scores using the same inclusive conditions as the ranking."""
    live = select(Race).where(select(Vote.id).join(User, User.id == Vote.user_id).where(Vote.race_id == Race.id, Vote.points.isnot(None), User.is_admin == False).exists())
    admin_qqs = select(User.qq).where(User.is_admin == True)
    historical = select(HistoricalRace).where(select(HistoricalScore.id).where(HistoricalScore.race_id == HistoricalRace.id, HistoricalScore.qq.not_in(admin_qqs)).exists())
    for model, query_name in ((Race, 'live'), (HistoricalRace, 'historical')):
        query = live if query_name == 'live' else historical
        for key in ('age_range', 'sex_restriction', 'race_grade', 'country', 'surface'):
            if filters.get(key):
                query = query.where(getattr(model, key).in_(filters[key]))
        for key, is_min in (('date_from', True), ('date_to', False)):
            if filters.get(key) is not None:
                query = query.where(model.date >= filters[key] if is_min else model.date <= filters[key])
        distance = func.cast(func.regexp_replace(Race.distance, '[^0-9]', '', 'g'), sa.Integer) if model is Race else HistoricalRace.distance
        count = select(func.count(RaceHorse.id)).where(RaceHorse.race_id == Race.id).correlate(Race).scalar_subquery() if model is Race else HistoricalRace.horse_count
        for key, column, is_min in (('distance_min', distance, True), ('distance_max', distance, False), ('horse_count_min', count, True), ('horse_count_max', count, False)):
            if filters.get(key) is not None:
                query = query.where(column >= filters[key] if is_min else column <= filters[key])
        if query_name == 'live':
            live = query
        else:
            historical = query
    live_races = (await db.execute(live)).scalars().all()
    historical_races = (await db.execute(historical)).scalars().all()
    items = [{'id': r.id if include_hidden or not r.is_hidden else None, 'name': r.name if include_hidden or not r.is_hidden else '未公开比赛', 'date': r.date.isoformat() if include_hidden or not r.is_hidden else '', 'source': 'live'} for r in live_races]
    items += [{'id': None, 'name': r.name, 'date': r.date.isoformat(), 'source': 'historical'} for r in historical_races]
    return sorted(items, key=lambda item: (item['date'], item['name']), reverse=True)
