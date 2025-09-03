"""
Base exception class for BetterBundle Python Worker
"""

from typing import Optional, Dict, Any


class BetterBundleException(Exception):
    """Base exception for all BetterBundle errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "exception_type": self.__class__.__name__,
        }


class DataStorageError(BetterBundleException):
    """Raised when data storage operations fail"""

    def __init__(
        self,
        message: str,
        operation: str = "unknown",
        data_type: str = "unknown",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, cause)
        self.operation = operation
        self.data_type = data_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        base_dict = super().to_dict()
        base_dict.update({"operation": self.operation, "data_type": self.data_type})
        return base_dict
