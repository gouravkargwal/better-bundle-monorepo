"""
Logging formatters for BetterBundle Python Worker
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured logs in a consistent format"""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)

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

        # Add module and function info
        if record.module:
            log_entry["module"] = record.module
        if record.funcName:
            log_entry["function"] = record.funcName
        if record.lineno:
            log_entry["line"] = record.lineno

        # Add process and thread info
        log_entry["process"] = record.process
        log_entry["thread"] = record.thread

        # Convert to formatted string
        return json.dumps(log_entry, default=str)


class JSONFormatter(logging.Formatter):
    """JSON formatter for machine-readable logs"""

    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        # Create JSON log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }

        # Add extra fields if they exist
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any additional attributes
        for key, value in record.__dict__.items():
            if key not in log_entry and not key.startswith("_"):
                try:
                    # Try to serialize the value
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    pass

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colors"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        # Get color for log level
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Format the message
        formatted = f"{color}[{timestamp}] {record.levelname:8s} {record.name}: {record.getMessage()}{reset}"

        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


class SimpleFormatter(logging.Formatter):
    """Simple, clean formatter for basic logging"""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        if fmt is None:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"

        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        # Format the basic message
        formatted = super().format(record)

        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted
