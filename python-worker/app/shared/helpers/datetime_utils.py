"""
DateTime utility functions for BetterBundle Python Worker
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
import pytz


def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def utcnow() -> datetime:
    """Backward-compatible alias for current UTC time.

    Several modules import `utcnow` from this helper. Provide a thin wrapper
    to avoid duplicate implementations and ensure timezone-aware datetimes.
    """
    return now_utc()


def parse_datetime(
    date_string: str,
    format_string: Optional[str] = None,
    timezone_name: Optional[str] = None,
) -> Optional[datetime]:
    """
    Parse datetime string with optional format and timezone

    Args:
        date_string: String to parse
        format_string: Optional format string (e.g., "%Y-%m-%d %H:%M:%S")
        timezone_name: Optional timezone name (e.g., "UTC", "America/New_York")

    Returns:
        Parsed datetime or None if parsing fails
    """
    try:
        if format_string:
            dt = datetime.strptime(date_string, format_string)
        else:
            # Try common formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
            ]

            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                return None

        # Apply timezone if specified
        if timezone_name:
            try:
                tz = pytz.timezone(timezone_name)
                dt = tz.localize(dt)
            except pytz.exceptions.UnknownTimeZoneError:
                # If timezone is invalid, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo is None:
            # If no timezone info, assume UTC
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except (ValueError, TypeError):
        return None


def format_datetime(
    dt: datetime,
    format_string: str = "%Y-%m-%d %H:%M:%S",
    timezone_name: Optional[str] = None,
) -> str:
    """
    Format datetime to string with optional timezone conversion

    Args:
        dt: Datetime to format
        format_string: Format string
        timezone_name: Optional timezone to convert to

    Returns:
        Formatted datetime string
    """
    if timezone_name:
        try:
            tz = pytz.timezone(timezone_name)
            dt = dt.astimezone(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            # If timezone is invalid, keep original
            pass

    return dt.strftime(format_string)


def time_ago(dt: datetime, reference: Optional[datetime] = None) -> timedelta:
    """
    Get time difference from reference time (defaults to now)

    Args:
        dt: Datetime to compare
        reference: Reference datetime (defaults to now)

    Returns:
        Time difference as timedelta
    """
    if reference is None:
        reference = now_utc()

    return reference - dt


def time_until(dt: datetime, reference: Optional[datetime] = None) -> timedelta:
    """
    Get time difference until target time (defaults to now)

    Args:
        dt: Target datetime
        reference: Reference datetime (defaults to now)

    Returns:
        Time difference as timedelta
    """
    if reference is None:
        reference = now_utc()

    return dt - reference


def is_business_day(dt: datetime) -> bool:
    """
    Check if datetime is a business day (Monday-Friday)

    Args:
        dt: Datetime to check

    Returns:
        True if business day, False otherwise
    """
    return dt.weekday() < 5  # Monday = 0, Friday = 4


def get_business_days_between(start_date: datetime, end_date: datetime) -> int:
    """
    Get number of business days between two dates

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of business days
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    business_days = 0
    current_date = start_date

    while current_date <= end_date:
        if is_business_day(current_date):
            business_days += 1
        current_date += timedelta(days=1)

    return business_days


def add_business_days(dt: datetime, business_days: int) -> datetime:
    """
    Add business days to datetime

    Args:
        dt: Starting datetime
        business_days: Number of business days to add

    Returns:
        New datetime
    """
    result = dt
    days_to_add = abs(business_days)
    direction = 1 if business_days > 0 else -1

    while days_to_add > 0:
        result += timedelta(days=direction)
        if is_business_day(result):
            days_to_add -= 1

    return result


def get_quarter_dates(year: int, quarter: int) -> tuple[datetime, datetime]:
    """
    Get start and end dates for a quarter

    Args:
        year: Year
        quarter: Quarter (1-4)

    Returns:
        Tuple of (start_date, end_date)
    """
    if quarter < 1 or quarter > 4:
        raise ValueError("Quarter must be between 1 and 4")

    quarter_starts = {
        1: (1, 1),  # January 1
        2: (4, 1),  # April 1
        3: (7, 1),  # July 1
        4: (10, 1),  # October 1
    }

    quarter_ends = {
        1: (3, 31),  # March 31
        2: (6, 30),  # June 30
        3: (9, 30),  # September 30
        4: (12, 31),  # December 31
    }

    start_month, start_day = quarter_starts[quarter]
    end_month, end_day = quarter_ends[quarter]

    start_date = datetime(year, start_month, start_day, tzinfo=timezone.utc)
    end_date = datetime(year, end_month, end_day, 23, 59, 59, tzinfo=timezone.utc)

    return start_date, end_date


def is_weekend(dt: datetime) -> bool:
    """
    Check if datetime is a weekend

    Args:
        dt: Datetime to check

    Returns:
        True if weekend, False otherwise
    """
    return dt.weekday() >= 5  # Saturday = 5, Sunday = 6


def get_month_start_end(dt: datetime) -> tuple[datetime, datetime]:
    """
    Get start and end of month for given datetime

    Args:
        dt: Datetime

    Returns:
        Tuple of (month_start, month_end)
    """
    month_start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1)

    month_end = next_month - timedelta(days=1)
    month_end = month_end.replace(hour=23, minute=59, second=59, microsecond=999999)

    return month_start, month_end
