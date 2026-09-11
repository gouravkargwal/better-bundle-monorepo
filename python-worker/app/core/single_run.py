"""
Run a periodic job in exactly one process, however many are running.

Why this exists
---------------
`uvicorn --workers N` forks N complete copies of the app, and each one runs the
whole lifespan in `app/main.py`. The four periodic jobs started there — the
enrichment sweeper, the attribution reconciler, the FX refresher and the
ingestion backstop — had no guard, so at `--workers 4` there were four ingestion
backstops asking Shopify for every shop's orders every 30 minutes, four
reconcilers sweeping the same rows, and four refreshers hitting a free FX API.
Four workers would each find the same missing order and each republish it.

It was invisible because dev runs `--reload`, which is a single worker.

Why a lock per cycle, and not leader election
---------------------------------------------
Electing one "leader" process at startup to own all four jobs is the obvious
design and a worse one:

  * A leader has to be re-elected when it dies, which means heartbeats,
    timeouts, and a window where nothing runs.
  * It pins every job to one process, so one worker does all the background
    work while the others idle.
  * It holds a lock for the process lifetime, which means holding a database
    connection for the process lifetime.

Locking per cycle needs none of that. Each job takes its own lock only while it
is actually running, so two jobs can run on two different workers, and there is
no leader to lose. If a worker dies mid-sweep its connection dies with it and
Postgres drops the lock immediately — the next cycle on any worker picks it up,
with no timeout to tune.

It also scales past this problem: the lock is held in Postgres, not in memory,
so it works the same for N workers in one container as for N containers on N
machines. Leader election inside a process would not.
"""

import hashlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text

from app.core.database.engine import get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)


def lock_key(name: str) -> int:
    """A stable signed 64-bit key for a job name.

    `pg_try_advisory_lock` takes a bigint, so the name has to be hashed down to
    one. Signed, because Postgres bigint is signed and an unsigned value above
    2^63 would be rejected.

    Stable across processes and restarts by construction — it is a pure function
    of the name, with no randomisation. Python's built-in `hash()` would NOT
    work here: it is salted per process (PYTHONHASHSEED), so every worker would
    compute a different key for the same job and every one of them would think
    it held the lock.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


@asynccontextmanager
async def claim(name: str) -> AsyncIterator[bool]:
    """Yield True in exactly one process cluster-wide, for the duration.

    Usage — note that the body must be skipped when it yields False:

        async with claim("ingestion_backstop") as mine:
            if mine:
                await sweep_once()

    Never raises on contention: losing the race is the normal outcome for
    every worker but one, and is not an error.

    A database failure is also not fatal here. It yields False, because the
    alternative — assuming the lock is ours when we could not check — is how you
    get the duplicate sweeps this module exists to prevent. Skipping one cycle
    is cheap; every job here re-runs on an interval.
    """
    key = lock_key(name)

    # Acquisition is guarded; the caller's body is NOT.
    #
    # An earlier version wrapped the whole thing in one try/except, which
    # swallowed exceptions raised by the body and re-reported them as lock
    # failures — so the four loops' own error handling never fired, and the
    # ingestion backstop's deliberately-loud webhook alarm was relabelled as a
    # database problem. Only the acquire may fail quietly here.
    conn = None
    try:
        engine = await get_engine()
        conn = await engine.connect()

        # engine.connect(), NOT a Session.
        #
        # This is the whole correctness of the module. `pg_try_advisory_lock` is
        # scoped to the SESSION, which in Postgres means the connection — and
        # `Session.commit()` does not merely end the transaction, it hands the
        # connection back to the pool. The lock goes back with it, the next
        # claim checks that same connection out again, and advisory locks are
        # re-entrant within a connection, so it succeeds too. Two workers, both
        # convinced they hold it.
        #
        # That was not hypothetical: the first version of this file committed a
        # Session after acquiring, to avoid holding a transaction open, and both
        # racers won the test.
        acquired = bool(
            (
                await conn.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                )
            ).scalar()
        )
        # Ends the transaction but keeps the connection checked out, so no
        # snapshot is pinned and vacuum is not blocked for the length of a
        # sweep. The lock lives on the connection, so it is unaffected.
        await conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"{name}: could not reach the lock, skipping cycle: {exc}")
        if conn is not None:
            await conn.close()
        yield False
        return

    if not acquired:
        logger.debug(f"{name}: another worker holds the lock, skipping")
        await conn.close()
        yield False
        return

    try:
        yield True
    finally:
        # Load-bearing. The connection goes back to the pool on close, and
        # SQLAlchemy's rollback-on-return does NOT release advisory locks — so
        # without this the lock leaks to the next borrower of that connection
        # and the job never runs again until a restart.
        #
        # `finally` so it runs when the body raises, and on the CancelledError
        # raised at shutdown. The body's exception still propagates.
        try:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": key}
            )
            await conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"{name}: failed to release advisory lock {key}: {exc}",
                exc_info=True,
            )
        finally:
            await conn.close()
