"""Race management business logic service."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.horse import Horse
from app.models.race import Race, RaceHorse, RaceStatus
from app.schemas.race import CustomScoring, RaceCreate, RaceUpdate


async def get_races(
    db: AsyncSession,
    status_filter: str | None = None,
    include_hidden: bool = False,
) -> list[Race]:
    """Get all races, optionally filtered by status."""
    stmt = (
        select(Race)
        .options(selectinload(Race.race_horses))
        .order_by(Race.date.desc(), Race.created_at.desc())
    )

    if not include_hidden:
        stmt = stmt.where(Race.is_hidden == False)

    if status_filter:
        try:
            valid_status = RaceStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_STATUS",
                    "message": f"无效的状态值: {status_filter}",
                },
            )
        stmt = stmt.where(Race.status == valid_status)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_race(
    db: AsyncSession,
    race_id: int,
    include_hidden: bool = False,
) -> Race | None:
    """Get a single race by ID with horses eagerly loaded."""
    stmt = (
        select(Race)
        .options(selectinload(Race.race_horses))
        .where(Race.id == race_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_race_vote_count(db: AsyncSession, race_id: int) -> int:
    """Get the number of votes for a race."""
    from app.models.vote import Vote

    stmt = select(func.count(Vote.id)).where(Vote.race_id == race_id)
    result = await db.execute(stmt)
    return result.scalar() or 0


def validate_custom_scoring(
    custom_scoring: CustomScoring | None, horse_count: int | None = None
) -> None:
    """Validate custom scoring data for CUSTOM grade races."""
    if custom_scoring is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CUSTOM_SCORING",
                "message": "自定义等级必须提供积分列表",
            },
        )
    if not custom_scoring.positive_scores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CUSTOM_SCORING",
                "message": "正序积分列表不能为空",
            },
        )
    if any(s <= 0 for s in custom_scoring.positive_scores):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CUSTOM_SCORING",
                "message": "正序积分必须为正数",
            },
        )
    if len(custom_scoring.positive_scores) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CUSTOM_SCORING",
                "message": "正序积分列表不能超过 50 项",
            },
        )
    if horse_count is not None and len(custom_scoring.positive_scores) < horse_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CUSTOM_SCORING",
                "message": f"正序积分列表数量 ({len(custom_scoring.positive_scores)}) 少于参赛马匹数 ({horse_count})",
            },
        )


def _build_snapshot(horse: Horse) -> dict:
    """Build a snapshot dict from a Horse ORM object."""
    return {
        "name": horse.name,
        "sex": horse.sex,
        "birth_year": horse.birth_year,
        "origin": horse.origin,
        "hemisphere": horse.hemisphere,
        "location": horse.location,
        "sire": horse.sire,
        "damsire": horse.damsire,
        "previous_result": horse.previous_result,
        "previous_result_date": str(horse.previous_result_date) if horse.previous_result_date else None,
        "previous_result_position": horse.previous_result_position,
        "best_win": horse.best_win,
        "best_win_date": str(horse.best_win_date) if horse.best_win_date else None,
    }


async def create_race(db: AsyncSession, data: RaceCreate) -> Race:
    """Create a new race with horse snapshots."""
    horse_ids = data.horse_ids or []

    if len(horse_ids) > 0 and len(horse_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INSUFFICIENT_HORSES",
                "message": "至少需要 2 匹参赛马",
            },
        )

    if data.race_grade == "自定义":
        validate_custom_scoring(data.custom_scoring, horse_count=len(horse_ids))

    custom_scoring_dict = (
        data.custom_scoring.model_dump() if data.custom_scoring else None
    )
    race = Race(
        name=data.name,
        date=data.date,
        age_range=data.age_range,
        sex_restriction=data.sex_restriction,
        race_grade=data.race_grade,
        country=data.country,
        distance=data.distance,
        surface=data.surface,
        status=RaceStatus.VOTING,
        custom_scoring=custom_scoring_dict,
        is_hidden=data.is_hidden,
    )
    db.add(race)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RACE_CREATE_CONFLICT",
                "message": "比赛创建失败，请重试",
            },
        )

    for index, horse_id in enumerate(horse_ids):
        horse = await db.get(Horse, horse_id)
        if not horse:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "HORSE_NOT_FOUND",
                    "message": f"马匹 {horse_id} 不存在",
                },
            )

        j = (
            data.horse_jockeys.get(str(horse_id)) or data.horse_jockeys.get(horse_id)
            if data.horse_jockeys
            else None
        )

        race_horse = RaceHorse(
            race_id=race.id,
            horse_id=horse.id,
            snapshot_data=_build_snapshot(horse),
            jockey=j,
            gate=index + 1,
        )
        db.add(race_horse)

    await db.flush()
    await db.refresh(race, ["race_horses"])
    return race


async def update_race(
    db: AsyncSession, race_id: int, data: RaceUpdate
) -> Race:
    """Update an existing race. Only voting races can be edited."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可编辑",
            },
        )

    update_data = data.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in update_data.items() if v is not None}

    vote_count = await get_race_vote_count(db, race_id)
    lockable_tags = {
        "age_range",
        "sex_restriction",
        "race_grade",
        "country",
        "distance",
        "surface",
    }
    if vote_count > 0 and lockable_tags & update_data.keys():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VOTES_EXIST",
                "message": "比赛已有投票，等级不可修改",
            },
        )

    if "name" in update_data:
        race.name = update_data["name"]
    if "date" in update_data:
        race.date = update_data["date"]

    for tag_field in (
        "age_range",
        "sex_restriction",
        "race_grade",
        "country",
        "distance",
        "surface",
    ):
        if tag_field in update_data:
            setattr(race, tag_field, update_data[tag_field])

    if "race_grade" in update_data:
        if update_data["race_grade"] == "自定义":
            if "custom_scoring" in update_data:
                scoring = update_data["custom_scoring"]
                validate_custom_scoring(
                    CustomScoring(**scoring), horse_count=len(race.race_horses)
                )
                race.custom_scoring = scoring
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "MISSING_CUSTOM_SCORING",
                        "message": "切换到自定义等级时必须提供积分列表",
                    },
                )
        else:
            race.custom_scoring = None

    if "horse_jockeys" in update_data:
        jockeys = update_data["horse_jockeys"]
        for rh in race.race_horses:
            j = jockeys.get(str(rh.id)) or jockeys.get(rh.id)
            if j is not None:
                rh.jockey = j

    if "horse_ids" in update_data:
        new_horse_ids = set(update_data["horse_ids"])
        existing_ids = {rh.horse_id for rh in race.race_horses}
        new_jockeys = (
            update_data.get("horse_jockeys", {})
            if "horse_jockeys" in update_data
            else {}
        )

        for horse_id in new_horse_ids - existing_ids:
            horse = await db.get(Horse, horse_id)
            if not horse:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "HORSE_NOT_FOUND",
                        "message": f"马匹 {horse_id} 不存在",
                    },
                )
            j = (
                new_jockeys.get(str(horse_id)) or new_jockeys.get(horse_id)
                if isinstance(new_jockeys, dict)
                else None
            )
            race_horse = RaceHorse(
                race_id=race.id,
                horse_id=horse.id,
                snapshot_data=_build_snapshot(horse),
                jockey=j,
            )
            db.add(race_horse)

        removed_rhs = [
            rh for rh in race.race_horses if rh.horse_id not in new_horse_ids
        ]
        if removed_rhs:
            from app.models.vote import Vote

            removed_rh_ids = [rh.id for rh in removed_rhs]
            vote_stmt = select(func.count(Vote.id)).where(
                Vote.race_id == race_id,
                Vote.race_horse_id.in_(removed_rh_ids),
            )
            vote_result = await db.execute(vote_stmt)
            vote_count_removed = vote_result.scalar() or 0
            if vote_count_removed > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "HORSE_HAS_VOTES",
                        "message": "无法移除已有投票的马匹",
                    },
                )
            for rh in removed_rhs:
                await db.delete(rh)

    await db.flush()
    race = await get_race(db, race.id)
    return race


async def add_horse_to_race(
    db: AsyncSession,
    race_id: int,
    horse_id: int,
    jockey: str | None = None,
) -> RaceHorse:
    """Add a single horse to a voting race."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )
    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可添加马匹",
            },
        )

    existing = [rh for rh in race.race_horses if rh.horse_id == horse_id]
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "HORSE_ALREADY_IN_RACE",
                "message": "该马匹已在比赛中",
            },
        )

    horse = await db.get(Horse, horse_id)
    if not horse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "HORSE_NOT_FOUND",
                "message": f"马匹 {horse_id} 不存在",
            },
        )

    max_gate = max((rh.gate or 0 for rh in race.race_horses), default=0)
    race_horse = RaceHorse(
        race_id=race.id,
        horse_id=horse.id,
        snapshot_data=_build_snapshot(horse),
        jockey=jockey,
        gate=max_gate + 1,
    )
    db.add(race_horse)
    await db.flush()
    await db.refresh(race_horse)
    return race_horse


async def update_race_horse(
    db: AsyncSession,
    race_id: int,
    race_horse_id: int,
    jockey: str | None = None,
) -> RaceHorse:
    """Update per-race jockey for a single RaceHorse."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )
    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可编辑马匹",
            },
        )

    race_horse = next(
        (rh for rh in race.race_horses if rh.id == race_horse_id), None
    )
    if race_horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RACE_HORSE_NOT_FOUND",
                "message": "比赛马匹不存在",
            },
        )

    race_horse.jockey = jockey

    await db.flush()
    await db.refresh(race_horse)
    return race_horse


async def refresh_race_horse_snapshot(
    db: AsyncSession,
    race_id: int,
    race_horse_id: int,
) -> RaceHorse:
    """Refresh a race horse's snapshot data from the latest Horse data."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可刷新马匹数据",
            },
        )

    race_horse = next(
        (rh for rh in race.race_horses if rh.id == race_horse_id), None
    )
    if race_horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RACE_HORSE_NOT_FOUND",
                "message": "比赛马匹不存在",
            },
        )

    horse = await db.get(Horse, race_horse.horse_id)
    if not horse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "HORSE_NOT_FOUND",
                "message": "马匹不存在",
            },
        )

    race_horse.snapshot_data = _build_snapshot(horse)
    await db.flush()
    await db.refresh(race_horse)
    return race_horse


async def update_gate_order(
    db: AsyncSession,
    race_id: int,
    order: list[int],
) -> Race:
    """Update gate numbers for all race horses based on the provided order."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )
    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可修改闸位",
            },
        )

    race_horse_map = {rh.id: rh for rh in race.race_horses}
    if set(order) != set(race_horse_map.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_GATE_ORDER",
                "message": "闸位排序必须包含所有参赛马匹",
            },
        )

    for gate, race_horse_id in enumerate(order, start=1):
        race_horse_map[race_horse_id].gate = gate

    await db.flush()
    await db.refresh(race, ["race_horses"])
    return race


async def remove_horse_from_race(
    db: AsyncSession,
    race_id: int,
    race_horse_id: int,
) -> None:
    """Remove a single horse from a voting race. Admin only."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status != RaceStatus.VOTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_NOT_EDITABLE",
                "message": "比赛已锁定/已结算，不可移除马匹",
            },
        )

    race_horse = next(
        (rh for rh in race.race_horses if rh.id == race_horse_id), None
    )
    if race_horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RACE_HORSE_NOT_FOUND", "message": "比赛马匹不存在"},
        )

    from app.models.vote import Vote

    vote_stmt = select(func.count(Vote.id)).where(
        Vote.race_id == race_id,
        Vote.race_horse_id == race_horse_id,
    )
    vote_result = await db.execute(vote_stmt)
    vote_count = vote_result.scalar() or 0
    if vote_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "HORSE_HAS_VOTES",
                "message": "无法移除已有投票的马匹",
            },
        )

    await db.delete(race_horse)
    await db.flush()


async def delete_race(db: AsyncSession, race_id: int) -> None:
    """Delete a race. Only non-settled races can be deleted."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    if race.status == RaceStatus.SETTLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RACE_SETTLED",
                "message": "已结算比赛不可删除",
            },
        )

    await db.delete(race)
    await db.flush()


async def toggle_race_hidden(db: AsyncSession, race_id: int) -> Race:
    """Toggle the is_hidden flag for a race. Admin only."""
    race = await get_race(db, race_id)
    if race is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "比赛不存在"},
        )

    race.is_hidden = not race.is_hidden
    await db.flush()
    await db.refresh(race, ["race_horses"])
    return race
