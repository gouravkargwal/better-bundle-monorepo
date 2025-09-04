"""
Database module for BetterBundle Python Worker
"""

from .simple_db_client import (
    get_database,
    close_database,
    check_database_health,
    with_database_retry,
    get_or_create_shop,
    clear_shop_data,
    update_shop_last_analysis,
    get_latest_timestamps,
)
from .health import reconnect_database

__all__ = [
    "get_database",
    "close_database",
    "check_database_health",
    "reconnect_database",
    "with_database_retry",
    "get_or_create_shop",
    "clear_shop_data",
    "update_shop_last_analysis",
    "get_latest_timestamps",
]
