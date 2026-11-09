import asyncio
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.models.historical_score import HistoricalImportBatch, HistoricalImportChange
from app.models.horse import Horse
from app.models.race import Race, RaceHorse, RaceStatus
from app.models.user import User
from app.models.vote import Vote
from app.schemas.auth import RegisterRequest
from app.schemas.result import ResultEntry, ResultPosition
from app.services import (
    auth_service,
    historical_management_service,
    invite_code_service,
    leaderboard_service,
    result_service,
    vote_service,
)
from app.services.historical_import_service import import_workbook, preview_workbook
from app.services.placeholder_user_service import (
    ensure_placeholders,
    remove_orphan_placeholders,
)
from tests.test_historical_import import workbook

pytestmark = pytest.mark.postgres

EXPECTED_BUSINESS_TABLES = {
    'users',
    'horses',
    'races',
    'race_horses',
    'votes',
    'historical_import_batches',
    'historical_import_changes',
    'historical_races',
    'historical_scores',
}


async def test_baseline_migration_upgrade_downgrade_and_zero_model_diff(pg_database):
    engine, sessions, migrate = pg_database
    await migrate()

    async with engine.connect() as conn:
        assert (await conn.execute(text('SELECT version_num FROM alembic_version'))).scalar_one() == '001'
        tables = set(
            (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"))).scalars()
        )
        assert tables - {'alembic_version'} == EXPECTED_BUSINESS_TABLES
        # No native enum type left in schema
        enums = (
            await conn.execute(
                text(
                    "SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
                    "WHERE n.nspname = current_schema() AND t.typtype = 'e'"
                )
            )
        ).scalars().all()
        assert enums == []

        def check_diffs(sync_conn):
            mc = MigrationContext.configure(
                sync_conn,
                opts={'compare_type': True, 'compare_server_default': True},
            )
            return compare_metadata(mc, Base.metadata)

        diffs = await conn.run_sync(check_diffs)
        assert diffs == []

    # Verify check constraint ck_races_status and global unique QQ index
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO races(name,date,age_range,sex_restriction,race_grade,country,distance,surface,status) "
                    "VALUES ('bad','2026-01-01','3岁','无','G1','日本',1600,'草地','INVALID')"
                )
            )

    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO users(username,qq) VALUES (NULL,'55555')"))
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO users(username,qq) VALUES ('dup','55555')"))

    # Verify downgrade('base') drops all 9 tables cleanly and upgrade('head') restores them
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / 'alembic.ini'))
    config.set_main_option('script_location', str(backend / 'alembic'))

    def do_downgrade(connection):
        config.attributes['connection'] = connection
        command.downgrade(config, 'base')

    async with engine.begin() as conn:
        await conn.run_sync(do_downgrade)

    async with engine.connect() as conn:
        remaining = set(
            (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"))).scalars()
        )
        assert remaining - {'alembic_version'} == set()

    await migrate()
    async with sessions() as db:
        assert await leaderboard_service.get_leaderboard(db) == []


async def test_concurrent_invite_creation_returns_one_conflict(pg_database, monkeypatch):
    _, sessions, migrate = pg_database
    await migrate()
    both_checked = asyncio.Barrier(2)
    check_existing = invite_code_service._raise_if_existing_qq_blocks

    async def check_existing_then_wait(db, qq):
        result = await check_existing(db, qq)
        await both_checked.wait()
        return result

    monkeypatch.setattr(invite_code_service, '_raise_if_existing_qq_blocks', check_existing_then_wait)

    async def create():
        async with sessions() as db:
            try:
                created = await invite_code_service.create_invite_code(db, '55555')
                await db.commit()
                return created.code
            except HTTPException as error:
                assert error.status_code == 409
                assert error.detail['code'] == 'QQ_HAS_UNUSED_CODE'
                return None

    results = await asyncio.wait_for(asyncio.gather(create(), create()), timeout=10)
    async with sessions() as db:
        codes = (await db.scalars(select(User.invite_code).where(User.invite_code.isnot(None)))).all()
    assert len(codes) == 1
    assert codes[0] in results and results.count(None) == 1


async def test_orphan_cleanup_cannot_delete_concurrently_activated_user(pg_database):
    _, sessions, migrate = pg_database
    await migrate()
    async with sessions() as db:
        await ensure_placeholders(db, {'55555': 'original'})
        placeholder = await db.scalar(select(User))
        await db.commit()

    async def cleanup():
        async with sessions() as db:
            removed = await remove_orphan_placeholders(db)
            await db.commit()
            return removed

    async with sessions() as db:
        registered = await auth_service.register(db, RegisterRequest(
            username='registered', password='secret123', qq=placeholder.qq, invite_code=placeholder.invite_code,
        ))
        task = asyncio.create_task(cleanup())
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), timeout=0.2)
        await db.commit()
    assert await asyncio.wait_for(task, timeout=10) == 0
    async with sessions() as db:
        activated = await db.get(User, registered.user.id)
        assert activated.username == 'registered'
        assert activated.password_hash is not None


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
        assert len((await db.scalars(select(HistoricalImportChange))).all()) == 1
        await historical_management_service.undo_batch(db, updated['batch_id'])
        await db.commit()
        # Batch and its change rows are physically deleted (ON DELETE CASCADE)
        assert await db.get(HistoricalImportBatch, updated['batch_id']) is None
        assert (await db.scalars(select(HistoricalImportChange))).all() == []
        assert (await leaderboard_service.get_leaderboard(db))[0].total_points == -5
        await historical_management_service.undo_batch(db, original['batch_id'])
        await db.commit()
        assert await db.get(HistoricalImportBatch, original['batch_id']) is None
        assert await leaderboard_service.get_leaderboard(db) == []


async def test_postgres_vote_lock_settle_resettle_and_distance_filter(pg_database):
    _, sessions, migrate = pg_database
    await migrate()
    async with sessions() as db:
        admin = User(username='admin', qq='90000', password_hash='test', invite_code=None, is_admin=True)
        user = User(username='player', qq='12345', password_hash='test', invite_code='PLAYER01', is_admin=False)
        horse = Horse(name='test horse')
        db.add_all([admin, user, horse]); await db.flush()
        race = Race(name='test race', date=date(2026, 1, 1), age_range='3岁', sex_restriction='无',
            race_grade='G1', country='日本', surface='草地', distance=1600, is_hidden=False)
        db.add(race); await db.flush()
        rh = RaceHorse(race_id=race.id, horse_id=horse.id, snapshot_data={'name': horse.name})
        db.add(rh); await db.commit()
        await vote_service.create_or_update_vote(db, race.id, user.id, rh.id)
        await db.commit()
        await vote_service.lock_race(db, race.id); await db.commit()
        with pytest.raises(HTTPException) as exc:
            await vote_service.delete_vote(db, race.id, user.id)
        assert exc.value.status_code == 400
        await result_service.submit_results(db, race.id, ResultEntry(positions=[ResultPosition(race_horse_id=rh.id, position=1)]))
        await db.commit()
        entries = await leaderboard_service.get_leaderboard(db, distance_min=1600, distance_max=1600, sort_by='avg_points')
        assert len(entries) == 1 and entries[0].total_points == 10
        assert len(await leaderboard_service.get_matching_races(db, distance_min=1600)) == 1
        assert await leaderboard_service.get_matching_races(db, distance_min=1601) == []
        await result_service.submit_results(db, race.id, ResultEntry(positions=[ResultPosition(race_horse_id=rh.id, position=0)]))
        await db.commit()
        score = (await db.execute(select(Vote.points).where(Vote.user_id == user.id))).scalar_one()
        assert score == 0 and race.status == RaceStatus.SETTLED
