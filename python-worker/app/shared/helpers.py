"""
Shared helper functions and utilities
"""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)
