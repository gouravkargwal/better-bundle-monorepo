"""
Drop leftover business indexes and create all tables.
Run this inside the container to fix the database state.
"""
import asyncio
from app.core.database.engine import get_engine
from sqlalchemy import text


async def fix():
    engine = await get_engine()

    # 1. Drop any leftover business indexes from partial runs
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT indexname, tablename FROM pg_indexes "
            "WHERE schemaname='public' "
            "AND indexname NOT LIKE 'auth_%' "
            "AND indexname NOT LIKE 'django_%' "
            "AND indexname NOT LIKE 'pg_%' "
            "AND tablename NOT IN ('feedback', 'items', 'users')"
        ))
        existing = [(r[0], r[1]) for r in result]

        if existing:
            print(f"Found {len(existing)} leftover indexes to drop:")
            for idx, tbl in existing:
                print(f"  Dropping {idx} on {tbl}...")
                await conn.execute(text(f'DROP INDEX IF EXISTS "{idx}"'))
            await conn.commit()
            print("✅ Dropped all leftover indexes")
        else:
            print("No leftover indexes found")

    await engine.dispose()

    # 2. Run create_all_tables
    print("\nRunning create_all_tables()...")
    from app.core.database.create_tables import create_all_tables
    result = await create_all_tables()
    print(f"Result: {result}")

    # 3. Verify tables
    engine2 = await get_engine()
    async with engine2.connect() as conn:
        result = await conn.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))
        tables = [row[0] for row in result]
        print(f"\nTotal tables now: {len(tables)}")
        for t in sorted(tables):
            print(f"  - {t}")

        # Check for key tables
        key_tables = [
            "shops", "commission_records", "scheduler_job_executions",
            "billing_cycles", "shop_subscriptions"
        ]
        print()
        for kt in key_tables:
            if kt in tables:
                print(f"  ✅ {kt}")
            else:
                print(f"  ❌ {kt} MISSING")

    await engine2.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
