"""
Structured logging configuration for the Python Worker
"""

import sys
import structlog
from typing import Any, Dict
from app.core.config import settings


def setup_logging() -> None:
    """Setup structured logging with consistent format"""

    # Configure structlog
    structlog.configure(
        processors=[
            # Filter out Postgres/Prisma passwords from logs
            structlog.stdlib.filter_by_level,
            # Add log level
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Add call site information
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # Format as JSON for production, console for development
            (
                structlog.dev.ConsoleRenderer()
                if settings.LOG_FORMAT == "console"
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def log_request_start(method: str, url: str, **kwargs) -> None:
    """Log the start of an HTTP request"""
    logger = get_logger("http.request")
    logger.info("Request started", method=method, url=url, **kwargs)


def log_request_end(
    method: str, url: str, status_code: int, duration_ms: float, **kwargs
) -> None:
    """Log the end of an HTTP request"""
    logger = get_logger("http.request")
    logger.info(
        "Request completed",
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        **kwargs
    )


def log_error(error: Exception, context: Dict[str, Any] = None, **kwargs) -> None:
    """Log an error with context"""
    logger = get_logger("error")
    logger.error(
        "Error occurred",
        error=str(error),
        error_type=type(error).__name__,
        context=context or {},
        **kwargs
    )


def log_performance(operation: str, duration_ms: float, **kwargs) -> None:
    """Log performance metrics"""
    logger = get_logger("performance")
    logger.info(
        "Performance metric", operation=operation, duration_ms=duration_ms, **kwargs
    )


def log_data_collection(
    shop_id: str,
    operation: str,
    items_count: int = None,
    duration_ms: float = None,
    **kwargs
) -> None:
    """Log data collection activities"""
    logger = get_logger("data.collection")
    logger.info(
        "Data collection activity",
        shop_id=shop_id,
        operation=operation,
        items_count=items_count,
        duration_ms=duration_ms,
        **kwargs
    )


def log_stream_event(
    stream_name: str, event_type: str, event_id: str = None, **kwargs
) -> None:
    """Log Redis stream events"""
    logger = get_logger("stream.event")
    logger.info(
        "Stream event",
        stream_name=stream_name,
        event_type=event_type,
        event_id=event_id,
        **kwargs
    )


def log_shopify_api(
    endpoint: str,
    method: str,
    status_code: int = None,
    duration_ms: float = None,
    shop_domain: str = None,
    **kwargs
) -> None:
    """Log Shopify API calls"""
    logger = get_logger("shopify.api")
    logger.info(
        "Shopify API call",
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        shop_domain=shop_domain,
        **kwargs
    )
