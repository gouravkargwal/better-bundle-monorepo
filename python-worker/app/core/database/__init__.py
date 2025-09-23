"""
Database module for BetterBundle Python Worker

Supports both Prisma (legacy) and SQLAlchemy async (new) database access patterns.
"""

# Legacy Prisma imports (for backward compatibility)
from .simple_db_client import (
    get_database as get_prisma_database,
    close_database as close_prisma_database,
    check_database_health as check_prisma_database_health,
    with_database_retry as prisma_with_database_retry,
    get_or_create_shop as prisma_get_or_create_shop,
    clear_shop_data as prisma_clear_shop_data,
    update_shop_last_analysis as prisma_update_shop_last_analysis,
    get_latest_timestamps as prisma_get_latest_timestamps,
)

# New SQLAlchemy async imports
from .engine import (
    get_engine,
    close_engine,
    check_engine_health,
    get_database_url,
    get_engine_context,
    # Backward compatibility functions
    get_database as get_sqlalchemy_database,
    close_database as close_sqlalchemy_database,
    check_database_health as check_sqlalchemy_database_health,
)

from .session import (
    get_session,
    get_session_factory,
    get_session_context,
    get_transaction_context,
    with_database_retry,
    database_retry,
    # Backward compatibility functions
    get_database,
    close_database,
    check_database_health,
)

from .health import reconnect_database

# Default exports (SQLAlchemy async)
__all__ = [
    # SQLAlchemy Engine
    "get_engine",
    "close_engine",
    "check_engine_health",
    "get_database_url",
    "get_engine_context",
    # SQLAlchemy Sessions
    "get_session",
    "get_session_factory",
    "get_session_context",
    "get_transaction_context",
    "with_database_retry",
    "database_retry",
    # Backward compatibility (defaults to SQLAlchemy)
    "get_database",
    "close_database",
    "check_database_health",
    # Health monitoring
    "reconnect_database",
    # Legacy Prisma (explicit imports)
    "get_prisma_database",
    "close_prisma_database",
    "check_prisma_database_health",
    "prisma_with_database_retry",
    "prisma_get_or_create_shop",
    "prisma_clear_shop_data",
    "prisma_update_shop_last_analysis",
    "prisma_get_latest_timestamps",
]
