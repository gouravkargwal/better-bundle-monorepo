"""
Core logging module for the Python Worker

This module provides a flexible logging system that can be easily extended
to support different logging backends like Grafana, Telemetry, GCP, or AWS.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.core.config import settings


class StructuredLogger:
    """Wrapper around standard Python logger that supports structured logging with keyword arguments."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with structured data as key=value pairs."""
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
        """Log debug message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.debug(formatted_message)

    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.info(formatted_message)

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.warning(formatted_message)

    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.error(formatted_message)

    def critical(self, message: str, **kwargs):
        """Log critical message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.critical(formatted_message)

    def exception(self, message: str, **kwargs):
        """Log exception message with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.exception(formatted_message)

    def log(self, level: int, message: str, **kwargs):
        """Log message at specified level with structured data."""
        formatted_message = self._format_message(message, **kwargs)
        self._logger.log(level, formatted_message)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured logs in a consistent format."""

    def format(self, record: logging.LogRecord) -> str:
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if they exist
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Format as pipe-separated key-value pairs for readability
        formatted_parts = []
        for key, value in log_entry.items():
            if value is not None:
                formatted_parts.append(f"{key}={value}")

        return " | ".join(formatted_parts)


class BaseLogHandler:
    """Base class for different logging backends."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.handler = None

    def get_handler(self) -> logging.Handler:
        """Return the configured logging handler."""
        raise NotImplementedError

    def is_enabled(self) -> bool:
        """Check if this handler is enabled."""
        return self.config.get("enabled", False)


class FileLogHandler(BaseLogHandler):
    """File-based logging handler."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.log_dir = Path(config.get("log_dir", "logs"))
        self.log_dir.mkdir(exist_ok=True)

        # Configure different log files for different levels
        self.handlers = {}

        # Main application log
        if config.get("app_log_enabled", True):
            app_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "app.log",
                maxBytes=config.get("max_file_size", 10 * 1024 * 1024),  # 10MB
                backupCount=config.get("backup_count", 5),
            )
            app_handler.setLevel(logging.INFO)
            self.handlers["app"] = app_handler

        # Error log
        if config.get("error_log_enabled", True):
            error_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "errors.log",
                maxBytes=config.get("max_file_size", 10 * 1024 * 1024),  # 10MB
                backupCount=config.get("backup_count", 5),
            )
            error_handler.setLevel(logging.ERROR)
            self.handlers["error"] = error_handler

        # Consumer log
        if config.get("consumer_log_enabled", True):
            consumer_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "consumer.log",
                maxBytes=config.get("max_file_size", 10 * 1024 * 1024),  # 10MB
                backupCount=config.get("backup_count", 5),
            )
            consumer_handler.setLevel(logging.INFO)
            self.handlers["consumer"] = consumer_handler

    def get_handlers(self) -> Dict[str, logging.Handler]:
        """Return all configured file handlers."""
        return self.handlers


class ConsoleLogHandler(BaseLogHandler):
    """Console/terminal logging handler."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setLevel(config.get("level", logging.INFO))

    def get_handler(self) -> logging.Handler:
        return self.handler


class PrometheusLogHandler(BaseLogHandler):
    """Prometheus metrics logging handler."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # This handler will integrate with prometheus-client
        # for metrics collection
        self.handler = None  # Prometheus doesn't need a traditional handler

    def get_handler(self) -> logging.Handler:
        # Return a no-op handler since Prometheus uses counters
        return logging.NullHandler()


class GrafanaLogHandler(BaseLogHandler):
    """Grafana Loki logging handler (placeholder for future implementation)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Future: Implement Grafana Loki client
        self.handler = None

    def get_handler(self) -> logging.Handler:
        # Placeholder - will implement actual Grafana integration
        return logging.NullHandler()


class TelemetryLogHandler(BaseLogHandler):
    """OpenTelemetry logging handler (placeholder for future implementation)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Future: Implement OpenTelemetry client
        self.handler = None

    def get_handler(self) -> logging.Handler:
        # Placeholder - will implement actual OpenTelemetry integration
        return logging.NullHandler()


class GCPLogHandler(BaseLogHandler):
    """Google Cloud Logging handler (placeholder for future implementation)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Future: Implement Google Cloud Logging client
        self.handler = None

    def get_handler(self) -> logging.Handler:
        # Placeholder - will implement actual GCP integration
        return logging.NullHandler()


class AWSLogHandler(BaseLogHandler):
    """AWS CloudWatch logging handler (placeholder for future implementation)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Future: Implement AWS CloudWatch client
        self.handler = None

    def get_handler(self) -> logging.Handler:
        # Placeholder - will implement actual AWS integration
        return logging.NullHandler()


class LoggerFactory:
    """Factory class for creating and configuring loggers."""

    def __init__(self):
        self.loggers = {}
        self._setup_logging()

    def _setup_logging(self):
        """Setup the logging configuration based on settings."""
        # Get logging configuration from settings
        log_config = getattr(settings, "LOGGING", {})

        # Create handlers
        handlers = []

        # File logging
        if log_config.get("file", {}).get("enabled", True):
            file_handler = FileLogHandler(log_config.get("file", {}))
            if file_handler.is_enabled():
                for name, handler in file_handler.get_handlers().items():
                    handler.setFormatter(StructuredFormatter())
                    handlers.append(handler)

        # Console logging
        if log_config.get("console", {}).get("enabled", True):
            console_handler = ConsoleLogHandler(log_config.get("console", {}))
            if console_handler.is_enabled():
                console_handler.get_handler().setFormatter(StructuredFormatter())
                handlers.append(console_handler.get_handler())

        # Prometheus logging
        if log_config.get("prometheus", {}).get("enabled", True):
            prometheus_handler = PrometheusLogHandler(log_config.get("prometheus", {}))
            if prometheus_handler.is_enabled():
                handlers.append(prometheus_handler.get_handler())

        # Future backends (currently disabled by default)
        future_handlers = [
            ("grafana", GrafanaLogHandler),
            ("telemetry", TelemetryLogHandler),
            ("gcp", GCPLogHandler),
            ("aws", AWSLogHandler),
        ]

        for name, handler_class in future_handlers:
            if log_config.get(name, {}).get("enabled", False):
                handler = handler_class(log_config.get(name, {}))
                if handler.is_enabled():
                    handlers.append(handler.get_handler())

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_config.get("level", logging.INFO))

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add new handlers
        for handler in handlers:
            root_logger.addHandler(handler)

    def get_logger(self, name: str) -> StructuredLogger:
        """Get or create a logger with the specified name."""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        return StructuredLogger(logger)


# Global logger factory instance
_logger_factory = None


def get_logger(name: str) -> StructuredLogger:
    """Get a logger instance with the specified name."""
    global _logger_factory
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
    return _logger_factory.get_logger(name)


def configure_logging(config: Optional[Dict[str, Any]] = None):
    """Reconfigure logging with new configuration."""
    global _logger_factory
    if config:
        # Update settings if config provided
        if hasattr(settings, "LOGGING"):
            settings.LOGGING.update(config)

    # Recreate logger factory with new configuration
    _logger_factory = LoggerFactory()
