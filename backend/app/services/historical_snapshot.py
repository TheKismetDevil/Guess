"""Canonical snapshots shared by preview, replacement and undo."""

from datetime import date

from sqlalchemy import delete, select

from app.models.historical_score import HistoricalScore
from app.models.user import User

FIELDS = (
    "name",
    "date",
    "age_range",
    "sex_restriction",
    "race_grade",
    "country",
    "surface",
    "distance",
    "horse_count",
)


def snapshot(metadata, scores):
    values = {key: metadata[key] for key in FIELDS}
    if isinstance(values["date"], date):
        values["date"] = values["date"].isoformat()
    canonical_scores = [
        {"qq": s["qq"], "points": s["points"]}
        for s in sorted(scores, key=lambda s: s["qq"])
    ]
    return {"metadata": values, "scores": canonical_scores}


async def current_snapshot(db, race):
    rows = (
        await db.execute(
            select(User.qq, HistoricalScore.points)
            .join(User, User.id == HistoricalScore.user_id)
            .where(HistoricalScore.race_id == race.id)
        )
    ).all()
    return snapshot(
        {key: getattr(race, key) for key in FIELDS},
        [{"qq": qq, "points": points} for qq, points in rows],
    )


async def apply_snapshot(db, race, state, qq_to_user_id: dict[str, int]):
    for key, value in state["metadata"].items():
        setattr(race, key, date.fromisoformat(value) if key == "date" else value)
    await db.execute(delete(HistoricalScore).where(HistoricalScore.race_id == race.id))
    for item in state["scores"]:
        db.add(
            HistoricalScore(
                race_id=race.id,
                user_id=qq_to_user_id[item["qq"]],
                points=item["points"],
            )
        )
    await db.flush()


def differences(before, after):
    changes = [
        dict(
            kind="metadata",
            field=key,
            before=before["metadata"][key],
            after=after["metadata"][key],
        )
        for key in FIELDS
        if before["metadata"][key] != after["metadata"][key]
    ]
    old = {s["qq"]: s for s in before["scores"]}
    new = {s["qq"]: s for s in after["scores"]}
    for qq in sorted(old.keys() | new.keys()):
        if old.get(qq) != new.get(qq):
            changes.append(
                dict(kind="score", qq=qq, before=old.get(qq), after=new.get(qq))
            )
    return changes
