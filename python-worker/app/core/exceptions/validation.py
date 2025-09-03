"""
Validation-related exceptions
"""

from typing import Any, Dict, Optional
from .base import BetterBundleException


class ValidationError(BetterBundleException):
    """Base exception for validation errors"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": value},
            **kwargs
        )


class DataValidationError(ValidationError):
    """Raised when data validation fails"""

    def __init__(
        self,
        message: str,
        validation_errors: list,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_ERROR",
            details={"validation_errors": validation_errors, "data": data},
            **kwargs
        )


class SchemaValidationError(ValidationError):
    """Raised when schema validation fails"""

    def __init__(self, message: str, schema: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="SCHEMA_VALIDATION_ERROR",
            details={"schema": schema},
            **kwargs
        )
