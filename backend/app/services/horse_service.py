"""Horse data management business logic service."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.horse import Horse
from app.schemas.horse import HorseCreate, HorseUpdate


async def get_horses(
    db: AsyncSession, name: str | None = None
) -> list[Horse]:
    """Get all horses, optionally filtered by name fuzzy search."""
    stmt = select(Horse).order_by(Horse.name.asc())

    if name:
        stmt = stmt.where(Horse.name.ilike(f"%{name}%"))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_horse(db: AsyncSession, horse_id: int) -> Horse | None:
    """Get a single horse by ID."""
    result = await db.execute(select(Horse).where(Horse.id == horse_id))
    return result.scalar_one_or_none()


async def create_horse(db: AsyncSession, data: HorseCreate) -> Horse:
    """Create a new horse.

    Raises 409 if a horse with the same name already exists.
    """
    existing = await db.execute(
        select(Horse).where(Horse.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "HORSE_NAME_EXISTS",
                "message": f"马匹「{data.name}」已存在",
            },
        )

    horse = Horse(**data.model_dump())
    db.add(horse)
    await db.flush()
    await db.refresh(horse)
    return horse


async def update_horse(
    db: AsyncSession, horse_id: int, data: HorseUpdate
) -> Horse:
    """Update a horse's attributes. Only provided fields are updated.

    Raises 404 if horse not found.
    Raises 409 if the new name conflicts with an existing horse.
    Raises 400 if previous_result provided without date or position.
    """
    horse = await get_horse(db, horse_id)
    if horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "马匹不存在"},
        )

    update_data = data.model_dump(exclude_unset=True)

    # If name is being changed, check for duplicates
    if "name" in update_data and update_data["name"] != horse.name:
        existing = await db.execute(
            select(Horse).where(Horse.name == update_data["name"])
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "HORSE_NAME_EXISTS",
                    "message": f"马匹「{update_data['name']}」已存在",
                },
            )

    # Validate that if previous_result/previous_result_date/previous_result_position
    # is provided, all must be present (partial not allowed)
    has_prev_result = "previous_result" in update_data
    has_prev_date = "previous_result_date" in update_data
    has_prev_pos = "previous_result_position" in update_data
    prev_fields_present = [has_prev_result, has_prev_date, has_prev_pos]
    if any(prev_fields_present) and not all(prev_fields_present):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INCOMPLETE_PREVIOUS_RESULT",
                "message": "前走成绩必须同时提供日期和名次",
            },
        )

    # Validate that if best_win/best_win_date is provided, both must be present
    has_best_win = "best_win" in update_data
    has_best_date = "best_win_date" in update_data
    if has_best_win != has_best_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INCOMPLETE_BEST_WIN",
                "message": "主要胜鞍必须同时提供比赛名称和日期",
            },
        )

    for field, value in update_data.items():
        setattr(horse, field, value)

    await db.flush()
    await db.refresh(horse)
    return horse


async def delete_horse(db: AsyncSession, horse_id: int) -> None:
    """Delete a horse.

    Raises 404 if horse not found.
    """
    horse = await get_horse(db, horse_id)
    if horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "马匹不存在"},
        )

    await db.delete(horse)
    await db.flush()


async def get_origins_stats(db: AsyncSession) -> list[dict]:
    """Get origin (country) usage frequency statistics with hemisphere info."""
    stmt = (
        select(Horse.origin, func.count(Horse.id).label("count"))
        .where(Horse.origin.isnot(None))
        .group_by(Horse.origin)
        .order_by(func.count(Horse.id).desc(), Horse.origin.asc())
    )
    result = await db.execute(stmt)
    rows = []
    for row in result.all():
        origin = row[0]
        hs = await _get_common_hemisphere(db, origin)
        rows.append({"origin": origin, "count": row[1], "hemisphere": hs})
    return rows


async def _get_common_hemisphere(db: AsyncSession, origin: str) -> str | None:
    """Get the most common hemisphere for a given origin."""
    stmt = (
        select(Horse.hemisphere, func.count(Horse.id).label("cnt"))
        .where(Horse.origin == origin, Horse.hemisphere.isnot(None))
        .group_by(Horse.hemisphere)
        .order_by(func.count(Horse.id).desc())
    )
    result = await db.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def get_locations_stats(db: AsyncSession) -> list[dict]:
    """Get location (training stable) usage frequency statistics."""
    stmt = (
        select(Horse.location, func.count(Horse.id).label("count"))
        .where(Horse.location.isnot(None))
        .group_by(Horse.location)
        .order_by(func.count(Horse.id).desc(), Horse.location.asc())
    )
    result = await db.execute(stmt)
    return [{"location": row[0], "count": row[1]} for row in result.all()]


async def toggle_hemisphere(db: AsyncSession, origin: str) -> dict:
    """Toggle hemisphere for all horses with the given origin."""
    stmt = select(Horse).where(Horse.origin == origin, Horse.hemisphere.isnot(None))
    result = await db.execute(stmt)
    horses = list(result.scalars().all())

    new_hs = None
    for h in horses:
        new_hs = "south" if h.hemisphere == "north" else "north"
        h.hemisphere = new_hs

    await db.flush()

    return {
        "origin": origin,
        "new_hemisphere": new_hs,
        "affected_count": len(horses),
    }


async def update_best_win(
    db: AsyncSession, horse_id: int, race_id: int
) -> Horse:
    """Update a horse's best_win to the specified race."""
    horse = await get_horse(db, horse_id)
    if horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "马匹不存在"},
        )

    from app.models.race import RaceHorse

    stmt = (
        select(RaceHorse)
        .options(selectinload(RaceHorse.race))
        .where(RaceHorse.horse_id == horse_id, RaceHorse.race_id == race_id)
    )
    result = await db.execute(stmt)
    rh = result.scalar_one_or_none()

    if rh is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "HORSE_NOT_IN_RACE",
                "message": "该马匹未参与此比赛",
            },
        )

    if rh.position != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "HORSE_NOT_WINNER",
                "message": "该马匹不是此比赛的胜马",
            },
        )

    horse.best_win = rh.race.name
    horse.best_win_date = rh.race.date
    await db.flush()
    await db.refresh(horse)
    return horse
