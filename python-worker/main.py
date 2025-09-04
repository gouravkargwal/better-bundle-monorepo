#!/usr/bin/env python3
"""
Main entry point for the Python Worker
"""

import uvicorn
import logging
from app.core.config import settings
from app.core.logging.logger import setup_logging
from app.core.logging.config import LoggingConfig

if __name__ == "__main__":
    # Setup our custom logging configuration
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

    # Setup logging before starting uvicorn
    setup_logging(logging_config)

    # Configure uvicorn to use our logging configuration
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,  # This will be 8001 from .env
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
        log_config=None,  # Disable uvicorn's default logging config
    )
