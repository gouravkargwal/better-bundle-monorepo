"""
Run Alembic migrations programmatically.

Called at startup so a container comes up with its schema current, which is the
behaviour the previous `create_all()` call provided. The difference is that
schema *changes* are now tracked and applied, where `create_all` silently
ignored any alteration to an existing table.

Note this runs migrations in-process on boot. That is fine for a single worker;
if the worker is ever scaled horizontally, two replicas starting together will
both try to migrate. Alembic takes a lock on its version table so one will
simply wait, but at that point it is cleaner to move this to an init container
or a deploy step and drop the startup call.
"""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.logging import get_logger

logger = get_logger(__name__)

# python-worker/ — the directory holding alembic.ini
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _config() -> Config:
    ini = PROJECT_ROOT / "alembic.ini"
    if not ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {ini}")
    cfg = Config(str(ini))
    # script_location is relative to alembic.ini, which is not necessarily the
    # process working directory.
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


def _upgrade_sync(revision: str = "head") -> None:
    command.upgrade(_config(), revision)


async def upgrade_to_head() -> bool:
    """Bring the database up to the latest revision.

    Alembic's API is synchronous and opens its own connection, so it runs in a
    worker thread to avoid blocking the event loop during startup.
    """
    try:
        await asyncio.to_thread(_upgrade_sync, "head")
        logger.info("✅ Database migrations up to date")
        return True
    except Exception as e:
        # A failed migration must not be swallowed: continuing would run the
        # app against a schema it does not expect, which fails later at query
        # time with nothing pointing at the cause.
        logger.error(f"❌ Database migration failed: {e}", exc_info=True)
        return False


def stamp_baseline() -> None:
    """Mark the baseline as applied without running it.

    For a database whose tables were created by the old `create_all()` path:
    the objects already exist, so the baseline must be recorded rather than
    executed. Run once, per environment.
    """
    command.stamp(_config(), "0001_baseline")
    logger.info("Stamped database at 0001_baseline")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stamp":
        stamp_baseline()
    else:
        asyncio.run(upgrade_to_head())
