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
)
from .formatters import JSONFormatter, ConsoleFormatter, sanitize_extra

# Global logger cache
_loggers: Dict[str, logging.Logger] = {}


class StructuredLogger:
    """Standard logger wrapper that emits keyword arguments as structured fields.

    kwargs go through logging's ``extra=`` rather than being concatenated into
    the message. That is what makes them queryable in OpenObserve: the OTel
    ``LoggingHandler`` copies every non-reserved LogRecord attribute into the
    log record's attributes, so ``logger.info("saved", shop_id=x)`` becomes a
    `shop_id` column you can filter and group by. Formatted into the message
    string — as this used to do — the same call produced free text that nothing
    can aggregate.

    Terminal output is unchanged: ConsoleFormatter re-renders the same fields as
    ``key=value`` at format time, so humans still see them inline.
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    # `/` makes message/level positional-only. Without it a caller's own field
    # named `message` or `level` — plausible things to log — binds to the
    # parameter instead of the kwargs and raises TypeError at runtime, in code
    # that was merely trying to describe itself.
    #
    # `exc_info` stays a real keyword rather than joining kwargs: ~30 call
    # sites pass it, all on error paths, and sweeping it into kwargs would
    # rename it to a `ctx_exc_info=True` field and drop the traceback —
    # losing the stack exactly where it is the entire point of the log line.
    def _log(self, level: int, message: str, /, *, exc_info: bool = False, **kwargs):
        extra = sanitize_extra(kwargs)
        self._logger.log(
            level, message, extra=extra, exc_info=exc_info, stacklevel=3
        )

    def debug(self, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(logging.DEBUG, message, exc_info=exc_info, **kwargs)

    def info(self, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(logging.INFO, message, exc_info=exc_info, **kwargs)

    def warning(self, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(logging.WARNING, message, exc_info=exc_info, **kwargs)

    def error(self, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def exception(self, message: str, /, **kwargs):
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

    def log(self, level: int, message: str, /, *, exc_info: bool = False, **kwargs):
        self._log(level, message, exc_info=exc_info, **kwargs)


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

    # Silence third-party loggers.
    #
    # The root logger carries an OTLP handler, so anything any dependency logs
    # is shipped and stored. At LOG_LEVEL=debug that means aiokafka's per-poll
    # chatter, SQLAlchemy's full statement echo and botocore's request signing
    # all land in OpenObserve alongside our own lines, where they are the bulk
    # of the volume and none of the signal. Only three libraries were pinned
    # here before; these are the ones that actually talk.
    for name in (
        "urllib3", "requests", "httpx", "httpcore", "hpack",
        "aiokafka", "kafka", "asyncio", "botocore", "boto3", "s3transfer",
        "sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects",
        "alembic", "multipart", "PIL", "matplotlib", "charset_normalizer",
        "opentelemetry", "google", "grpc", "openai", "anthropic",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn's access log duplicates what the FastAPI instrumentation already
    # records as a span and a metric, with none of the attributes.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

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
