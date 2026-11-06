from datetime import date
from io import BytesIO

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import select, text

from app.models.horse import Horse
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.schemas.result import ResultEntry, ResultPosition
from app.services import historical_management_service, leaderboard_service, result_service, vote_service
from app.services.historical_import_service import import_workbook, preview_workbook
from tests.test_historical_import import workbook

pytestmark = pytest.mark.postgres


async def test_all_migrations_and_legacy_backfill_preserve_scores(pg_database):
    engine, _, migrate = pg_database
    await migrate('016')
    async with engine.begin() as conn:
        await conn.execute(text("""INSERT INTO historical_races
            (id,name,date,age_range,sex_restriction,race_grade,country,surface,distance,horse_count)
            VALUES (1,'legacy','2026-01-01','3岁','无','G1','日本','草地',1600,12)"""))
        await conn.execute(text("INSERT INTO historical_scores(race_id,qq,display_name,points) VALUES (1,'12345','legacy user',0)"))
    await migrate()
    async with engine.connect() as conn:
        assert (await conn.execute(text('SELECT version_num FROM alembic_version'))).scalar_one() == '018'
        assert (await conn.execute(text('SELECT points FROM historical_scores'))).scalar_one() == 0
        assert (await conn.execute(text('SELECT count(*) FROM historical_races WHERE import_batch_id IS NOT NULL'))).scalar_one() == 1
        assert (await conn.execute(text('SELECT imported_races, imported_scores, updated_races FROM historical_import_batches'))).one() == (1, 1, 0)


async def test_postgres_import_diff_update_and_undo(pg_database):
    _, sessions, migrate = pg_database
    await migrate()
    async with sessions() as db:
        original = await import_workbook(db, workbook())
        await db.commit()
        w = load_workbook(BytesIO(workbook()))
        w['历史得分']['C2'] = 9
        out = BytesIO(); w.save(out); w.close()
        content = out.getvalue()
        preview = await preview_workbook(db, content)
        item = next(r for r in preview['races'] if r['action'] == 'conflict')
        updated = await import_workbook(db, content, preview_token=preview['preview_token'], decisions={str(item['race_id']): 'replace'})
        await db.commit()
        assert (await leaderboard_service.get_leaderboard(db))[0].total_points == 4
        await historical_management_service.undo_batch(db, updated['batch_id'])
        await db.commit()
        assert (await leaderboard_service.get_leaderboard(db))[0].total_points == -5
        await historical_management_service.undo_batch(db, original['batch_id'])
        await db.commit()
        assert await leaderboard_service.get_leaderboard(db) == []


async def test_postgres_vote_lock_settle_resettle_and_distance_filter(pg_database):
    _, sessions, migrate = pg_database
    await migrate()
    async with sessions() as db:
        admin = User(username='admin', qq='90000', password_hash='test', invite_code='ADMIN', is_admin=True)
        user = User(username='player', qq='12345', password_hash='test', invite_code='PLAYER', is_admin=False)
        horse = Horse(name='test horse')
        db.add_all([admin, user, horse]); await db.flush()
        race = Race(name='test race', date=date(2026, 1, 1), age_range='3岁', sex_restriction='无',
            race_grade='G1', country='日本', surface='草地', distance='1600m', creator_id=admin.id, is_hidden=False)
        db.add(race); await db.flush()
        rh = RaceHorse(race_id=race.id, horse_id=horse.id, snapshot_data={'name': horse.name})
        db.add(rh); await db.commit()
        await vote_service.create_or_update_vote(db, race.id, user.id, rh.id)
        await db.commit()
        await vote_service.lock_race(db, race.id); await db.commit()
        with pytest.raises(HTTPException) as exc:
            await vote_service.delete_vote(db, race.id, user.id)
        assert exc.value.status_code == 400
        await result_service.submit_results(db, race.id, ResultEntry(positions=[ResultPosition(race_horse_id=rh.id, position=1)]), admin.id)
        await db.commit()
        entries = await leaderboard_service.get_leaderboard(db, distance_min=1600, distance_max=1600, sort_by='avg_points')
        assert len(entries) == 1 and entries[0].total_points == 10
        assert len(await leaderboard_service.get_matching_races(db, distance_min=1600)) == 1
        assert await leaderboard_service.get_matching_races(db, distance_min=1601) == []
        await result_service.submit_results(db, race.id, ResultEntry(positions=[ResultPosition(race_horse_id=rh.id, position=0)]), admin.id)
        await db.commit()
        score = (await db.execute(select(Vote.points).where(Vote.user_id == user.id))).scalar_one()
        assert score == 0 and race.status == RaceStatus.SETTLED
