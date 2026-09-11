import os

import pytest

import asyncio

import pytest_asyncio


# One event loop for the whole test session.
#
# pytest-asyncio 0.21 gives every test a fresh loop and closes it afterwards.
# That was harmless while the engine used NullPool — there was no pool, so
# nothing outlived a loop. Now that the engine pools connections (see
# app/core/database/engine.py, where removing NullPool took a database round
# trip from 14.6ms to 0.9ms), a connection opened on test A's loop is still in
# the pool when test B runs on a new one, and asyncpg fails with
# "Event loop is closed".
#
# A session-scoped loop is pytest-asyncio 0.21's documented answer, and it is
# the better one here for a second reason: the tests now exercise the same
# pooled configuration production runs, instead of silently testing a setup
# nobody deploys.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Dispose the engine before that loop closes, or SQLAlchemy tries to terminate
# pooled connections against a dead loop and the run ends in a wall of
# "Future exception was never retrieved".
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_engine_at_end():
    yield
    from app.core.database.engine import close_database

    await close_database()



SHOP_ID = "shop_42"
SHOP_DOMAIN = "test.myshopify.com"
USER_ID = "cust_123"
PRODUCT_IDS = ["prod_001", "prod_002", "prod_003"]

@pytest.fixture
def sample_gorse_items():
    return [
        {"Id": f"shop_{SHOP_ID}_{pid}", "Score": 0.9 - i * 0.1}
        for i, pid in enumerate(PRODUCT_IDS)
    ]
