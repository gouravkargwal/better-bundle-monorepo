"""
Alembic environment.

Two things differ from the generated default:

1. **The URL comes from application settings, not alembic.ini.** Migrations then
   always target the same database the app does, and no credential sits in a
   tracked file.

2. **The engine is async** (asyncpg), so migrations run inside
   `connection.run_sync`. Alembic's own machinery is synchronous.

`pgvector.sqlalchemy` is imported for its side effect: autogenerate needs the
`Vector` type registered to render `product_vectors.vector`, and generated
migrations import it by name.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Registers the pgvector type so autogenerate can see it.
import pgvector.sqlalchemy  # noqa: F401

# Importing the package registers every model on Base.metadata. Without this
# autogenerate sees an empty schema and cheerfully proposes dropping every table.
from app.core.database.models import Base  # noqa: E402
import app.core.database.models  # noqa: F401,E402
from app.core.config.settings import settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """The application's own DSN."""
    return settings.database.DATABASE_URL


def include_object(obj, name, type_, reflected, compare_to):
    """Keep autogenerate away from things it should not manage.

    pgvector creates its own index types, and Prisma owns nothing here — but
    the `alembic_version` table itself must never be diffed.
    """
    if type_ == "table" and name == "alembic_version":
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it. `alembic upgrade head --sql`."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        # Catch column type and default changes, not just added/dropped columns.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
