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
)
