"""Result entry business logic — drag-sort result submission and settlement."""

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.horse import Horse
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.vote import Vote
from app.schemas.result import ResultEntry, UserScoreItem
from app.services.scoring_engine import calculate_score, derive_scoring_grade


async def submit_results(
    db: AsyncSession, race_id: int, data: ResultEntry
) -> dict:
    """Submit race results — transition from locked to settled.

    If race is already settled, this re-settles (rollback + recalculate).
    All operations happen in a single transaction.
    """
    stmt = (
        select(Race)
        .options(
            selectinload(Race.race_horses),
            selectinload(Race.votes).selectinload(Vote.user),
        )
        .where(Race.id == race_id)
    )
    result = await db.execute(stmt)
    race = result.scalar_one_or_none()

    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status == RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_LOCKED",
                "message": "比赛处于投票中状态，请先锁定",
            },
        )

    # Build position lookup: race_horse_id -> position
    position_map: dict[int, int] = {
        entry.race_horse_id: entry.position for entry in data.positions
    }

    # Validate all race_horses are accounted for
    race_horse_ids = {rh.id for rh in race.race_horses}
    submitted_ids = set(position_map.keys())

    if submitted_ids != race_horse_ids:
        missing = race_horse_ids - submitted_ids
        extra = submitted_ids - race_horse_ids
        msg_parts = []
        if missing:
            msg_parts.append(f"缺少马匹: {missing}")
        if extra:
            msg_parts.append(f"多余的马匹: {extra}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_POSITIONS",
                "message": "; ".join(msg_parts),
            },
        )

    if race.status == RaceStatus.SETTLED:
        for vote in race.votes:
            vote.points = None

    # Update RaceHorse positions
    for rh in race.race_horses:
        rh.position = position_map[rh.id]

    # Calculate active horse count (position > 0)
    active_count = sum(1 for p in position_map.values() if p > 0)

    # Calculate scores for each vote
    for vote in race.votes:
        vote_rh = next(
            (rh for rh in race.race_horses if rh.id == vote.race_horse_id),
            None,
        )
        if vote_rh is None:
            vote.points = 0
        elif vote_rh.position is not None and vote_rh.position > 0:
            vote.points = calculate_score(
                grade=derive_scoring_grade(race.age_range, race.race_grade),
                total_horses=active_count,
                position=vote_rh.position,
                custom_scoring=race.custom_scoring,
            )
        else:
            vote.points = 0

    race.status = RaceStatus.SETTLED
    await db.flush()

    user_scores = [
        UserScoreItem(
            user_id=vote.user_id,
            username=vote.user.username if vote.user and vote.user.username else "未知",
            points=vote.points if vote.points is not None else 0,
        )
        for vote in race.votes
    ]

    # Auto-update previous_result for horses when race.date >= horse's previous_result_date
    try:
        for rh in race.race_horses:
            horse_obj = await db.get(Horse, rh.horse_id)
            if horse_obj is None:
                continue

            prev_date = horse_obj.previous_result_date
            if prev_date is None or race.date >= prev_date:
                pos_text = (
                    f"{rh.position}着"
                    if rh.position and rh.position > 0
                    else "除外/取消"
                )
                horse_obj.previous_result = f"{race.name} {pos_text}"
                horse_obj.previous_result_date = race.date
                horse_obj.previous_result_position = rh.position if rh.position else 0

        await db.flush()
    except Exception:
        logging.warning("Auto-update failed after settlement (non-blocking)", exc_info=True)

    return {
        "race_id": race.id,
        "status": race.status.value,
        "scores": user_scores,
    }
