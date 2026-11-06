"""Canonical snapshots shared by preview, replacement and undo."""
from datetime import date
from sqlalchemy import delete, select
from app.models.historical_score import HistoricalScore

FIELDS = ('name', 'date', 'age_range', 'sex_restriction', 'race_grade', 'country', 'surface', 'distance', 'horse_count')


def snapshot(metadata, scores):
    values = {key: metadata[key] for key in FIELDS}
    if isinstance(values['date'], date):
        values['date'] = values['date'].isoformat()
    return {'metadata': values, 'scores': sorted(scores, key=lambda s: s['qq'])}


async def current_snapshot(db, race):
    scores = (await db.execute(select(HistoricalScore).where(HistoricalScore.race_id == race.id))).scalars().all()
    return snapshot({key: getattr(race, key) for key in FIELDS},
        [dict(qq=s.qq, display_name=s.display_name, points=s.points) for s in scores])


async def apply_snapshot(db, race, state):
    for key, value in state['metadata'].items():
        setattr(race, key, date.fromisoformat(value) if key == 'date' else value)
    await db.execute(delete(HistoricalScore).where(HistoricalScore.race_id == race.id))
    for item in state['scores']:
        db.add(HistoricalScore(race_id=race.id, **item))
    await db.flush()


def differences(before, after):
    changes = [dict(kind='metadata', field=key, before=before['metadata'][key], after=after['metadata'][key])
        for key in FIELDS if before['metadata'][key] != after['metadata'][key]]
    old = {s['qq']: s for s in before['scores']}
    new = {s['qq']: s for s in after['scores']}
    for qq in sorted(old.keys() | new.keys()):
        if old.get(qq) != new.get(qq):
            changes.append(dict(kind='score', qq=qq, before=old.get(qq), after=new.get(qq)))
    return changes
