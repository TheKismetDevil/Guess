"""Vote business logic service."""

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.race import Race, RaceHorse, RaceStatus
from app.models.vote import Vote


async def create_or_update_vote(
    db: AsyncSession, race_id: int, user_id: int, race_horse_id: int
) -> tuple[Vote, int]:
    """Create a new vote or update an existing one for the same race.

    Returns (Vote, status_code) where status_code is 201 for new or 200 for update.
    Handles concurrent upsert via IntegrityError catch-and-retry.
    """
    stmt = select(Race).where(Race.id == race_id)
    result = await db.execute(stmt)
    race = result.scalar_one_or_none()
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )
    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VOTE_LOCKED", "message": "投票已截止"},
        )

    stmt = select(RaceHorse).where(
        RaceHorse.id == race_horse_id, RaceHorse.race_id == race_id
    )
    result = await db.execute(stmt)
    race_horse = result.scalar_one_or_none()
    if race_horse is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_HORSE", "message": "马匹不属于该比赛"},
        )

    stmt = select(Vote).where(Vote.user_id == user_id, Vote.race_id == race_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    try:
        if existing:
            existing.race_horse_id = race_horse_id
            vote = existing
            status_code = 200
        else:
            vote = Vote(
                user_id=user_id,
                race_id=race_id,
                race_horse_id=race_horse_id,
            )
            db.add(vote)
            status_code = 201

        await db.flush()
    except IntegrityError:
        await db.rollback()
        stmt = select(Vote).where(Vote.user_id == user_id, Vote.race_id == race_id)
        result = await db.execute(stmt)
        vote = result.scalar_one()
        vote.race_horse_id = race_horse_id
        await db.flush()
        await db.refresh(vote)
        return vote, 200

    stmt = (
        select(Vote)
        .options(selectinload(Vote.race_horse_rel))
        .where(Vote.id == vote.id)
    )
    result = await db.execute(stmt)
    vote = result.scalar_one()
    return vote, status_code


async def get_race_votes(db: AsyncSession, race_id: int) -> list[Vote]:
    """Get all votes for a race with user and horse info eager loaded."""
    stmt = (
        select(Vote)
        .options(
            selectinload(Vote.user),
            selectinload(Vote.race_horse_rel),
        )
        .where(Vote.race_id == race_id)
        .order_by(Vote.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def resolve_horse_name(vote: Vote) -> str:
    """Extract horse name from the vote's race_horse_rel snapshot data."""
    if vote.race_horse_rel and vote.race_horse_rel.snapshot_data:
        name = vote.race_horse_rel.snapshot_data.get("name")
        return name if name else "未知"
    return "未知"


async def delete_vote(
    db: AsyncSession, race_id: int, user_id: int
) -> None:
    """Delete a user's vote for a race if the race is still in VOTING status."""
    stmt = select(Race).where(Race.id == race_id)
    result = await db.execute(stmt)
    race = result.scalar_one_or_none()
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )
    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VOTE_LOCKED", "message": "投票已截止，无法取消"},
        )

    stmt = select(Vote).where(Vote.user_id == user_id, Vote.race_id == race_id)
    result = await db.execute(stmt)
    vote = result.scalar_one_or_none()
    if vote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VOTE_NOT_FOUND", "message": "你尚未投票"},
        )

    await db.delete(vote)
    await db.flush()


async def lock_race(db: AsyncSession, race_id: int) -> Race:
    """Lock voting for a race — transition from VOTING to LOCKED."""
    stmt = select(Race).where(Race.id == race_id)
    result = await db.execute(stmt)
    race = result.scalar_one_or_none()
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status != RaceStatus.VOTING:
        code = "RACE_LOCKED" if race.status == RaceStatus.LOCKED else "RACE_SETTLED"
        msg = "比赛已锁定" if race.status == RaceStatus.LOCKED else "比赛已结算，无法锁定"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code, "message": msg},
        )

    race.status = RaceStatus.LOCKED
    await db.flush()
    await db.refresh(race)
    return race


async def get_race_results_grouped_by_horse(
    db: AsyncSession, race_id: int
) -> list[dict]:
    """For a settled race, load all votes grouped by race_horse_id."""
    stmt = (
        select(RaceHorse)
        .options(
            selectinload(RaceHorse.votes).selectinload(Vote.user),
        )
        .where(RaceHorse.race_id == race_id)
        .order_by(
            case(
                (RaceHorse.position == 0, 2),
                (RaceHorse.position.is_(None), 3),
                else_=1,
            ),
            RaceHorse.position.asc().nulls_last(),
        )
    )
    result = await db.execute(stmt)
    race_horses = list(result.scalars().all())

    output = []
    for rh in race_horses:
        votes = [
            {
                "username": v.user.username if v.user and v.user.username else "unknown",
                "points": v.points,
            }
            for v in rh.votes
        ]
        output.append(
            {
                "race_horse_id": rh.id,
                "horse_id": rh.horse_id,
                "snapshot_data": rh.snapshot_data,
                "position": rh.position,
                "jockey": rh.jockey,
                "votes": votes,
            }
        )
    return output
