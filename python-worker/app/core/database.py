"""
Database connection and utilities using Prisma Python

This module provides backward compatibility by re-exporting functions from the new simplified database client.
"""

# Re-export all functions from the simplified database client for backward compatibility
from app.core.database.simple_db_client import (
    get_database,
    close_database,
    check_database_health,
    with_database_retry,
    get_or_create_shop,
    clear_shop_data,
    update_shop_last_analysis,
    get_latest_timestamps,
)
