"""Tests use a dedicated test database and a fresh random schema per test."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def pg_database():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run PostgreSQL integration tests')
    parsed = make_url(url)
    if parsed.drivername != 'postgresql+asyncpg' or not (parsed.database or '').endswith('_test'):
        pytest.fail('TEST_DATABASE_URL must use postgresql+asyncpg and a database ending in _test')
    schema = 'test_guess_' + uuid4().hex
    admin_engine = create_async_engine(url)
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    backend = Path(__file__).resolve().parents[2]

    async def migrate(revision='head'):
        config = Config(str(backend / 'alembic.ini'))
        config.set_main_option('script_location', str(backend / 'alembic'))
        def upgrade(connection):
            config.attributes['connection'] = connection
            command.upgrade(config, revision)
        async with engine.begin() as conn:
            await conn.run_sync(upgrade)
    try:
        yield engine, async_sessionmaker(engine, expire_on_commit=False), migrate
    finally:
        await engine.dispose()
        # schema is generated locally, never derived from the connection URL or input.
        assert schema.startswith('test_guess_') and schema[11:].isalnum()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()
