"""
Database module for BetterBundle Python Worker

Uses SQLAlchemy async for all database operations.
"""

# New SQLAlchemy async imports
from .engine import (
    get_engine,
    close_engine,
    check_engine_health,
    get_database_url,
    get_engine_context,
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
]
