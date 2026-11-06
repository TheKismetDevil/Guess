"""Admin-only historical result management. Never changes live races or users."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import delete, func, select, or_
from app.models.historical_score import HistoricalImportBatch, HistoricalImportChange, HistoricalRace, HistoricalScore
from app.services.historical_snapshot import current_snapshot, apply_snapshot


def not_found():
    return HTTPException(404, detail={'code': 'NOT_FOUND', 'message': '历史记录不存在'})


async def list_batches(db):
    batches = (await db.execute(select(HistoricalImportBatch).order_by(HistoricalImportBatch.id.desc()))).scalars().all()
    return [dict(id=b.id, filename=b.filename, created_at=b.created_at, undone_at=b.undone_at,
                 race_count=b.imported_races, score_count=b.imported_scores, updated_races=b.updated_races) for b in batches]


async def batch_races(db, batch_id):
    batch = await db.get(HistoricalImportBatch, batch_id)
    if batch is None:
        raise not_found()
    if batch.undone_at is not None:
        return []
    updated_ids = select(HistoricalImportChange.race_id).where(HistoricalImportChange.batch_id == batch_id)
    rows = (await db.execute(select(HistoricalRace, func.count(HistoricalScore.id))
        .outerjoin(HistoricalScore, HistoricalScore.race_id == HistoricalRace.id)
        .where(or_(HistoricalRace.import_batch_id == batch_id, HistoricalRace.id.in_(updated_ids))).group_by(HistoricalRace.id)
        .order_by(HistoricalRace.date, HistoricalRace.id))).all()
    return [dict(id=r.id, name=r.name, date=r.date, score_count=count) for r, count in rows]


async def race_scores(db, race_id):
    if await db.get(HistoricalRace, race_id) is None:
        raise not_found()
    scores = (await db.execute(select(HistoricalScore).where(HistoricalScore.race_id == race_id)
        .order_by(HistoricalScore.qq))).scalars().all()
    return [dict(id=s.id, qq=s.qq, display_name=s.display_name, points=s.points) for s in scores]


async def update_score(db, score_id, points, expected_points):
    race_id = (await db.execute(select(HistoricalScore.race_id).where(HistoricalScore.id == score_id))).scalar_one_or_none()
    if race_id is None:
        raise not_found()
    await db.execute(select(HistoricalRace).where(HistoricalRace.id == race_id).with_for_update())
    score = (await db.execute(select(HistoricalScore).where(HistoricalScore.id == score_id)
        .with_for_update())).scalar_one_or_none()
    if score is None:
        raise not_found()
    if score.points != expected_points:
        raise HTTPException(409, detail={'code': 'SCORE_CHANGED', 'message': '该成绩已被修改，请重新加载后再保存'})
    score.points = points
    await db.flush()
    return dict(id=score.id, qq=score.qq, display_name=score.display_name, points=score.points)


async def undo_batch(db, batch_id):
    batch = (await db.execute(select(HistoricalImportBatch).where(HistoricalImportBatch.id == batch_id)
        .with_for_update())).scalar_one_or_none()
    if batch is None:
        raise not_found()
    if batch.undone_at is not None:
        return {'removed_races': 0, 'removed_scores': 0, 'restored_races': 0}
    changes = (await db.execute(select(HistoricalImportChange).where(HistoricalImportChange.batch_id == batch_id))).scalars().all()
    changed_ids = [change.race_id for change in changes]
    affected = (await db.execute(select(HistoricalRace).where(or_(HistoricalRace.import_batch_id == batch_id,
        HistoricalRace.id.in_(changed_ids))).order_by(HistoricalRace.id).with_for_update())).scalars().all()
    later_change = (await db.execute(select(HistoricalImportChange.id).join(HistoricalImportBatch)
        .where(HistoricalImportChange.race_id.in_([r.id for r in affected]),
            HistoricalImportBatch.id > batch_id, HistoricalImportBatch.undone_at.is_(None)).limit(1))).first()
    if later_change:
        raise HTTPException(409, detail={'code': 'LATER_IMPORT_EXISTS', 'message': '这些比赛还有后续导入更新，请先撤销后续批次'})
    by_id = {r.id: r for r in affected}
    for change in changes:
        race = by_id.get(change.race_id)
        if race is None or await current_snapshot(db, race) != change.after:
            raise HTTPException(409, detail={'code': 'UNDO_CONFLICT', 'message': '成绩在导入后已被修改，无法直接撤销，请先核对当前成绩'})
    for change in changes:
        await apply_snapshot(db, by_id[change.race_id], change.before)
    race_ids = select(HistoricalRace.id).where(HistoricalRace.import_batch_id == batch_id)
    # Explicit deletion also works in SQLite tests where FK cascades are disabled.
    scores = await db.execute(delete(HistoricalScore).where(HistoricalScore.race_id.in_(race_ids)))
    races = await db.execute(delete(HistoricalRace).where(HistoricalRace.import_batch_id == batch_id))
    batch.undone_at = datetime.now(timezone.utc)
    await db.flush()
    return {'removed_races': races.rowcount, 'removed_scores': scores.rowcount, 'restored_races': len(changes)}
