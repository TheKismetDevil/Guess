"""
One-time script to delete all races (cascades to race_horses and votes).

Usage:
    cd backend
    python scripts/delete_all_races.py

WARNING: This will delete ALL race data including:
  - Races
  - RaceHorses (per-race horse entries)
  - Votes (all user votes)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.race import Race


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(Race))
        races = list(result.scalars().all())

        if not races:
            print("[SKIP] No races found — nothing to delete.")
            return

        print(f"[INFO] Found {len(races)} race(s).")
        for r in races:
            print(f"  - #{r.id}: {r.name} ({r.date})")

        confirm = input(f"\nDelete all {len(races)} races? This CANNOT be undone. Type 'yes': ")
        if confirm != "yes":
            print("[ABORT] Deletion cancelled.")
            return

        for race in races:
            await db.delete(race)

        await db.commit()
        print(f"[DONE] Deleted {len(races)} race(s) and all related data.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
