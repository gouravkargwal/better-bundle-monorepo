"""
Database connection and utilities using SQLAlchemy async

This module provides backward compatibility by re-exporting functions from the new SQLAlchemy setup.
"""

# Re-export all functions from the new SQLAlchemy setup for backward compatibility
from app.core.database import (
    get_database,
    close_database,
    check_database_health,
    with_database_retry,
    # Legacy Prisma functions (if needed)
    get_prisma_database,
    close_prisma_database,
    check_prisma_database_health,
    prisma_with_database_retry,
    prisma_get_or_create_shop,
    prisma_clear_shop_data,
    prisma_update_shop_last_analysis,
    prisma_get_latest_timestamps,
)
