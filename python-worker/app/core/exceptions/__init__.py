"""
Custom exceptions for the BetterBundle Python Worker
"""

from .base import BetterBundleException, DataStorageError
from .config import (
    ConfigurationError,
    EnvironmentVariableError,
    ConfigurationValidationError,
)
from .database import DatabaseError, DatabaseConnectionError, DatabaseQueryError
from .redis import RedisError, RedisConnectionError, RedisStreamError
from .validation import ValidationError, DataValidationError

__all__ = [
    "BetterBundleException",
    "ConfigurationError",
    "EnvironmentVariableError",
    "ConfigurationValidationError",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    "RedisError",
    "RedisConnectionError",
    "RedisStreamError",
    "ValidationError",
    "DataValidationError",
    "DataStorageError",
]
