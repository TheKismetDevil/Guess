"""Horse data management business logic service."""

from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.horse import Horse
from app.schemas.horse import HorseCreate, HorseUpdate


def _hemisphere_label(hemisphere: str) -> str:
    return "南半球" if hemisphere == "south" else "北半球"


async def _get_existing_origin_hemisphere(
    db: AsyncSession, origin: str
) -> str | None:
    """Return the established hemisphere for ``origin``, if any horse has one."""
    stmt = (
        select(Horse.hemisphere)
        .where(Horse.origin == origin, Horse.hemisphere.isnot(None))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _backfill_origin_hemisphere(
    db: AsyncSession, origin: str, hemisphere: str
) -> None:
    """Ensure any legacy horse of the same origin with NULL hemisphere matches."""
    await db.execute(
        update(Horse)
        .where(Horse.origin == origin, Horse.hemisphere.is_(None))
        .values(hemisphere=hemisphere)
    )


async def _resolve_origin_hemisphere_for_create(
    db: AsyncSession, origin: str | None, hemisphere: str | None
) -> str | None:
    if origin is None:
        if hemisphere is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ORIGIN_REQUIRED_FOR_HEMISPHERE",
                    "message": "未设置出生国时不能单独设置半球",
                },
            )
        return None

    existing_hs = await _get_existing_origin_hemisphere(db, origin)
    if existing_hs is not None:
        if hemisphere is not None and hemisphere != existing_hs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ORIGIN_HEMISPHERE_CONFLICT",
                    "message": f"出生国「{origin}」已绑定为{_hemisphere_label(existing_hs)}，如需更改请使用切换半球功能",
                },
            )
        return existing_hs

    if hemisphere is not None:
        await _backfill_origin_hemisphere(db, origin, hemisphere)
    return hemisphere


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

    Raises 409 if a horse with the same name already exists, or if the
    requested hemisphere conflicts with the origin's established hemisphere.
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

    payload = data.model_dump()
    payload["hemisphere"] = await _resolve_origin_hemisphere_for_create(
        db, payload["origin"], payload["hemisphere"]
    )

    horse = Horse(**payload)
    db.add(horse)
    await db.flush()
    await db.refresh(horse)
    return horse


async def update_horse(
    db: AsyncSession, horse_id: int, data: HorseUpdate
) -> Horse:
    """Update a horse's attributes. Only provided fields are updated.

    Raises 404 if horse not found.
    Raises 409 if the new name conflicts with an existing horse, or if the
    hemisphere conflicts with the origin's established hemisphere.
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

    # Enforce origin <-> hemisphere consistency
    if "origin" in update_data or "hemisphere" in update_data:
        target_origin = (
            update_data["origin"] if "origin" in update_data else horse.origin
        )
        if target_origin is None:
            if update_data.get("hemisphere") is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "ORIGIN_REQUIRED_FOR_HEMISPHERE",
                        "message": "未设置出生国时不能单独设置半球",
                    },
                )
            update_data["hemisphere"] = None
        else:
            existing_hs = await _get_existing_origin_hemisphere(db, target_origin)
            if "hemisphere" in update_data:
                req_hs = update_data["hemisphere"]
                if existing_hs is not None and req_hs != existing_hs:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "ORIGIN_HEMISPHERE_CONFLICT",
                            "message": f"出生国「{target_origin}」已绑定为{_hemisphere_label(existing_hs)}，如需更改请使用切换半球功能",
                        },
                    )
                if req_hs is not None and existing_hs is None:
                    await _backfill_origin_hemisphere(db, target_origin, req_hs)
            elif existing_hs is not None:
                # Origin changed without explicit hemisphere -> inherit target origin's hemisphere
                update_data["hemisphere"] = existing_hs

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
    """Get origin (country) usage frequency statistics with its unified hemisphere."""
    stmt = (
        select(
            Horse.origin,
            func.count(Horse.id).label("count"),
            func.max(Horse.hemisphere).label("hemisphere"),
        )
        .where(Horse.origin.isnot(None))
        .group_by(Horse.origin)
        .order_by(func.count(Horse.id).desc(), Horse.origin.asc())
    )
    result = await db.execute(stmt)
    return [
        {"origin": row[0], "count": row[1], "hemisphere": row[2]}
        for row in result.all()
    ]


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
    """Toggle hemisphere uniformly for all horses with the given origin."""
    origin = origin.strip()
    stmt = select(Horse).where(Horse.origin == origin)
    result = await db.execute(stmt)
    horses = list(result.scalars().all())
    if not horses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"出生国「{origin}」暂无关联马匹",
            },
        )

    non_null = [h.hemisphere for h in horses if h.hemisphere in ("north", "south")]
    current_hs = Counter(non_null).most_common(1)[0][0] if non_null else "south"
    new_hs = "south" if current_hs == "north" else "north"

    for h in horses:
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
