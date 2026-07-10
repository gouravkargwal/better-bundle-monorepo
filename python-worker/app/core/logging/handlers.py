"""
Logging handlers for BetterBundle Python Worker
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any

from .formatters import (
    StructuredFormatter,
    JSONFormatter,
    ConsoleFormatter,
    SimpleFormatter,
)


class FileHandler:
    """File handler factory for different log types"""

    @staticmethod
    def create_app_handler(
        log_dir: str = "logs",
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        level: int = logging.INFO,
        formatter_type: str = "console",
    ) -> logging.handlers.RotatingFileHandler:
        """Create application log handler"""
        os.makedirs(log_dir, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )

        handler.setLevel(level)

        # Set formatter based on type
        if formatter_type == "console":
            handler.setFormatter(ConsoleFormatter())
        elif formatter_type == "json":
            handler.setFormatter(JSONFormatter())
        elif formatter_type == "structured":
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(SimpleFormatter())

        return handler

    @staticmethod
    def create_error_handler(
        log_dir: str = "logs",
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        formatter_type: str = "console",
    ) -> logging.handlers.RotatingFileHandler:
        """Create error log handler"""
        os.makedirs(log_dir, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "errors.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )

        handler.setLevel(logging.ERROR)

        # Set formatter based on type
        if formatter_type == "console":
            handler.setFormatter(ConsoleFormatter())
        elif formatter_type == "json":
            handler.setFormatter(JSONFormatter())
        elif formatter_type == "structured":
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(SimpleFormatter())

        return handler

    @staticmethod
    def create_consumer_handler(
        log_dir: str = "logs",
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        level: int = logging.INFO,
        formatter_type: str = "console",
    ) -> logging.handlers.RotatingFileHandler:
        """Create consumer log handler"""
        os.makedirs(log_dir, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "consumer.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )

        handler.setLevel(level)

        # Set formatter based on type
        if formatter_type == "console":
            handler.setFormatter(ConsoleFormatter())
        elif formatter_type == "json":
            handler.setFormatter(JSONFormatter())
        elif formatter_type == "structured":
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(SimpleFormatter())

        return handler


class ConsoleHandler:
    """Console handler factory"""

    @staticmethod
    def create_handler(
        level: int = logging.INFO, formatter_type: str = "console"
    ) -> logging.StreamHandler:
        """Create console handler with specified formatter"""
        handler = logging.StreamHandler()
        handler.setLevel(level)

        if formatter_type == "console":
            handler.setFormatter(ConsoleFormatter())
        elif formatter_type == "json":
            handler.setFormatter(JSONFormatter())
        elif formatter_type == "structured":
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(SimpleFormatter())

        return handler


class OpenObserveHandler:
    """OpenObserve logging handler (Loki-compatible API, replaces Grafana/Loki)"""

    @staticmethod
    def create_handler(url: str, email: str = "", password: str = "", org_id: str = "default"):
        """Create OpenObserve Loki-compatible handler"""
        try:
            import requests
            from .loki_handler import LokiHandler

            if not url:
                return None

            # Build full Loki-compatible push URL
            # OpenObserve accepts Loki format at: /api/<org>/loki/api/v1/push
            if url.endswith("/"):
                url = url.rstrip("/")

            if not url.endswith("/loki/api/v1/push"):
                url = f"{url}/api/{org_id}/loki/api/v1/push"

            return LokiHandler(url=url, username=email, password=password)
        except ImportError:
            print("Warning: requests library not available for OpenObserve handler")
            return None
        except Exception as e:
            print(f"Warning: Failed to create OpenObserve handler: {e}")
            return None
