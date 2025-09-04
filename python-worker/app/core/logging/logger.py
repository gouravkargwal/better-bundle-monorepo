"""
Main logging module for BetterBundle Python Worker
"""

import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path

from app.core.config.settings import Settings
from .config import LoggingConfig
from .handlers import (
    FileHandler,
    ConsoleHandler,
    PrometheusHandler,
    GrafanaHandler,
    TelemetryHandler,
    GCPHandler,
    AWSHandler,
)
from .formatters import JSONFormatter, ConsoleFormatter

# Global logger cache
_loggers: Dict[str, logging.Logger] = {}


class StructuredLogger:
    """Wrapper around standard Python logger that supports structured logging with keyword arguments"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with structured data as key=value pairs"""
        if not kwargs:
            return message

        # Convert kwargs to structured format
        structured_parts = []
        for key, value in kwargs.items():
            if value is not None:
                # Handle different value types
                if isinstance(value, (dict, list)):
                    structured_parts.append(f"{key}={str(value)}")
                elif isinstance(value, str) and " " in value:
                    # Quote strings with spaces
                    structured_parts.append(f'{key}="{value}"')
                else:
                    structured_parts.append(f"{key}={value}")

        if structured_parts:
            return f"{message} | {' | '.join(structured_parts)}"
        return message

    def debug(self, message: str, **kwargs):
        """Log debug message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.debug(formatted_message)

    def info(self, message: str, **kwargs):
        """Log info message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.info(formatted_message)

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.warning(formatted_message)

    def error(self, message: str, **kwargs):
        """Log error message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.error(formatted_message)

    def critical(self, message: str, **kwargs):
        """Log critical message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.critical(formatted_message)

    def exception(self, message: str, **kwargs):
        """Log exception message with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.exception(formatted_message)

    def log(self, level: int, message: str, **kwargs):
        """Log message at specified level with structured data"""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.log(level, formatted_message)


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """Setup logging configuration for the application"""
    if config is None:
        config = LoggingConfig()

    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Add file handlers if enabled
    if config.file.enabled:
        if config.file.app_log_enabled:
            app_handler = FileHandler.create_app_handler(
                log_dir=config.file.log_dir,
                max_bytes=config.file.max_file_size,
                backup_count=config.file.backup_count,
                level=getattr(logging, config.level.upper()),
                formatter_type=config.format,
            )
            root_logger.addHandler(app_handler)

        if config.file.error_log_enabled:
            error_handler = FileHandler.create_error_handler(
                log_dir=config.file.log_dir,
                max_bytes=config.file.max_file_size,
                backup_count=config.file.backup_count,
                formatter_type=config.format,
            )
            root_logger.addHandler(error_handler)

        if config.file.consumer_log_enabled:
            consumer_handler = FileHandler.create_consumer_handler(
                log_dir=config.file.log_dir,
                max_bytes=config.file.max_file_size,
                backup_count=config.file.backup_count,
                level=getattr(logging, config.level.upper()),
                formatter_type=config.format,
            )
            root_logger.addHandler(consumer_handler)

    # Add console handler if enabled
    if config.console.enabled:
        console_handler = ConsoleHandler.create_handler(
            level=getattr(logging, config.console.level.upper()),
            formatter_type=config.format,
        )
        root_logger.addHandler(console_handler)

    # Add Prometheus handler if enabled
    if config.prometheus.enabled:
        prometheus_handler = PrometheusHandler.create_handler(
            port=config.prometheus.port, metrics_path=config.prometheus.metrics_path
        )
        if prometheus_handler:
            root_logger.addHandler(prometheus_handler)

    # Add external service handlers if enabled
    if config.grafana.enabled:
        grafana_handler = GrafanaHandler.create_handler(
            config.grafana.url, config.grafana.username, config.grafana.password
        )
        if grafana_handler:
            root_logger.addHandler(grafana_handler)

    if config.telemetry.enabled:
        telemetry_handler = TelemetryHandler.create_handler(
            config.telemetry.endpoint, config.telemetry.service_name
        )
        if telemetry_handler:
            root_logger.addHandler(telemetry_handler)

    if config.gcp.enabled:
        gcp_handler = GCPHandler.create_handler(
            config.gcp.project_id, config.gcp.log_name
        )
        if gcp_handler:
            root_logger.addHandler(gcp_handler)

    if config.aws.enabled:
        aws_handler = AWSHandler.create_handler(
            config.aws.region, config.aws.log_group, config.aws.log_stream
        )
        if aws_handler:
            root_logger.addHandler(aws_handler)

    # Disable propagation for external loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info("Logging system initialized")


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    if name not in _loggers:
        # Create new logger
        logger = logging.getLogger(name)
        _loggers[name] = logger

    return StructuredLogger(_loggers[name])


def get_standard_logger(name: str) -> logging.Logger:
    """Get a standard Python logger instance"""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)

    return _loggers[name]


def set_log_level(name: str, level: str) -> None:
    """Set log level for a specific logger"""
    if name in _loggers:
        _loggers[name].setLevel(getattr(logging, level.upper()))
    else:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper()))
        _loggers[name] = logger


def add_handler_to_logger(name: str, handler: logging.Handler) -> None:
    """Add a handler to a specific logger"""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)

    _loggers[name].addHandler(handler)


def remove_handler_from_logger(name: str, handler: logging.Handler) -> None:
    """Remove a handler from a specific logger"""
    if name in _loggers:
        _loggers[name].removeHandler(handler)


# Initialize logging on module import
try:
    # Create settings instance
    settings = Settings()

    # Get logging config from settings
    logging_config = LoggingConfig(
        level=settings.logging.LOG_LEVEL,
        format=settings.logging.LOG_FORMAT,
        file=settings.logging.LOGGING["file"],
        console=settings.logging.LOGGING["console"],
        prometheus=settings.logging.LOGGING["prometheus"],
        grafana=settings.logging.LOGGING["grafana"],
        telemetry=settings.logging.LOGGING["telemetry"],
        gcp=settings.logging.LOGGING["gcp"],
        aws=settings.logging.LOGGING["aws"],
    )

    # Setup logging
    setup_logging(logging_config)

except Exception as e:
    # Fallback to basic logging if setup fails
    print(f"Failed to setup logging: {e}")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
