"""
Database-related exceptions
"""

from .base import BetterBundleException
from typing import Optional, Dict, Any


class DatabaseError(BetterBundleException):
    """Base exception for database errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details,
            cause=cause
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails"""
    
    def __init__(self, message: str, connection_details: Optional[Dict[str, Any]] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        connection_details_dict = {"connection_details": connection_details}
        if details:
            connection_details_dict.update(details)
        super().__init__(
            message=message,
            error_code="DATABASE_CONNECTION_ERROR",
            details=connection_details_dict,
            cause=cause
        )


class DatabaseQueryError(DatabaseError):
    """Raised when a database query fails"""
    
    def __init__(self, message: str, query: Optional[str] = None, params: Optional[Dict[str, Any]] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        query_details = {"query": query, "params": params}
        if details:
            query_details.update(details)
        super().__init__(
            message=message,
            error_code="DATABASE_QUERY_ERROR",
            details=query_details,
            cause=cause
        )


class DatabaseTransactionError(DatabaseError):
    """Raised when a database transaction fails"""
    
    def __init__(self, message: str, transaction_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        transaction_details = {"transaction_id": transaction_id}
        if details:
            transaction_details.update(details)
        super().__init__(
            message=message,
            error_code="DATABASE_TRANSACTION_ERROR",
            details=transaction_details,
            cause=cause
        )
