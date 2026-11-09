"""Compare scored race intersections using stable participant identities."""
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.security import opaque_key
from app.models.user import User
from app.models.vote import Vote
from app.models.race import Race, RaceStatus
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.services.avatar_service import avatar_key
from app.services.leaderboard_service import filter_race_query


async def participant_catalog(db):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    admin_qqs = {u.qq for u in users if u.is_admin}
    by_qq = defaultdict(list)
    catalog = {}
    for user in users:
        if user.is_admin:
            continue
        by_qq[user.qq].append(user)
        key = f'user:{user.id}'
        catalog[key] = dict(id=key, username=user.username, kind='user', user_id=user.id, history_qq=None,
            avatar_key=avatar_key(user.qq))
    for qq, matches in by_qq.items():
        if len(matches) == 1 and qq not in admin_qqs:
            catalog[f'user:{matches[0].id}']['history_qq'] = qq
    historical = (await db.execute(select(HistoricalScore.qq, func.max(HistoricalScore.display_name))
        .group_by(HistoricalScore.qq))).all()
    for qq, name in historical:
        if qq in admin_qqs or len(by_qq[qq]) == 1:
            continue
        key = opaque_key('history', qq)
        catalog[key] = dict(id=key, username=name, kind='historical', user_id=None, history_qq=qq,
            avatar_key=avatar_key(qq))
    return catalog


def public_participant(item):
    return {key: item[key] for key in ('id', 'username', 'kind', 'avatar_key')}


async def get_participants(db):
    catalog = await participant_catalog(db)
    return [public_participant(p) for p in sorted(catalog.values(), key=lambda p: (p['username'], p['id']))]


async def compare(db, participant_ids: list[str], include_hidden=False, **filters):
    if len(participant_ids) < 2 or len(set(participant_ids)) != len(participant_ids):
        raise HTTPException(400, detail={'code': 'INVALID_PARTICIPANTS', 'message': '请选择至少两位不同的用户'})
    catalog = await participant_catalog(db)
    if any(key not in catalog for key in participant_ids):
        raise HTTPException(400, detail={'code': 'UNKNOWN_PARTICIPANT', 'message': '所选用户已变化，请重新加载用户列表'})
    selected = [catalog[key] for key in participant_ids]
    items = []
    for model, scores_model, column, identity_key, source in (
        (Race, Vote, Vote.user_id, 'user_id', 'live'),
        (HistoricalRace, HistoricalScore, HistoricalScore.qq, 'history_qq', 'historical'),
    ):
        identities = [p[identity_key] for p in selected]
        if None in identities or len(set(identities)) != len(identities):
            continue
        common = (select(scores_model.race_id).where(column.in_(identities), scores_model.points.isnot(None))
            .group_by(scores_model.race_id).having(func.count(func.distinct(column)) == len(selected)))
        query = select(model).where(model.id.in_(common))
        if model is Race:
            query = query.where(Race.status == RaceStatus.SETTLED)
        races = (await db.execute(filter_race_query(query, model, filters))).scalars().all()
        if not races:
            continue
        points = (await db.execute(select(scores_model.race_id, column, scores_model.points)
            .where(scores_model.race_id.in_([r.id for r in races]), column.in_(identities)))).all()
        by_race = defaultdict(dict)
        for race_id, participant, score in points:
            by_race[race_id][participant] = score
        for race in races:
            hidden = model is Race and race.is_hidden and not include_hidden
            items.append(dict(key=opaque_key('hidden', str(race.id)) if hidden else f'{source}:{race.id}',
                id=race.id if source == 'live' and not hidden else None,
                name='未公开比赛' if hidden else race.name,
                date='' if hidden else race.date.isoformat(), source=source,
                scores=[by_race[race.id][identity] for identity in identities]))
    items.sort(key=lambda item: (item['date'], item['name'], item['key']), reverse=True)
    return {'participants': [public_participant(p) for p in selected], 'races': items}
