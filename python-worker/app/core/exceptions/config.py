"""
Configuration-related exceptions
"""

from .base import BetterBundleException
from typing import Optional


class ConfigurationError(BetterBundleException):
    """Raised when there's a configuration error"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        config_details = {"config_key": config_key}
        if details:
            config_details.update(details)
        super().__init__(
            message,
            "CONFIG_ERROR",
            config_details,
            cause,
        )


class EnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing"""

    def __init__(
        self,
        var_name: str,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        env_details = {"missing_variable": var_name}
        if details:
            env_details.update(details)
        super().__init__(
            message=f"Required environment variable '{var_name}' is not set",
            config_key=var_name,
            details=env_details,
            cause=cause,
        )


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration validation fails"""

    def __init__(
        self,
        message: str,
        validation_errors: list,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        validation_details = {"validation_errors": validation_errors}
        if details:
            validation_details.update(details)
        super().__init__(
            message,
            "CONFIG_VALIDATION_ERROR",
            validation_details,
            cause,
        )
