"""
DateTime utility functions for BetterBundle Python Worker
"""

from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse ISO timestamp string to timezone-aware datetime object.
    Handles both 'Z' suffix and '+00:00' formats for UTC timestamps.

    Args:
        timestamp_str: ISO timestamp string (e.g., "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00+00:00")

    Returns:
        timezone-aware datetime object or None if parsing fails
    """
    try:
        if timestamp_str.endswith("Z"):
            # Convert 'Z' suffix to explicit '+00:00' for proper timezone parsing
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            # Already has timezone info or is naive
            return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return None
