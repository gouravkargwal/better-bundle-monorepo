"""
Logging formatters for BetterBundle Python Worker
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional


# LogRecord attributes the stdlib owns. Passing any of these through ``extra=``
# raises KeyError inside logging itself, so a caller's ``logger.info(msg,
# module="billing")`` would take down the call site it was meant to describe.
# They are prefixed rather than dropped: the value the caller wanted to record
# still reaches OpenObserve, under a name that cannot collide.
RESERVED_ATTRS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "stacklevel", "thread", "threadName",
        "taskName",
    }
)


def sanitize_extra(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Make caller kwargs safe to pass as logging's ``extra``.

    Drops Nones (an absent value is not a field) and renames anything that
    would collide with a stdlib LogRecord attribute.
    """
    # `extra={...}` is the stdlib's own idiom and 25 call sites use it. Left
    # in kwargs it would arrive as a single column literally named `extra`
    # holding a dict — the nested blob that cannot be filtered on, which is
    # the whole failure this function exists to avoid. Merged, both styles
    # produce identical, queryable top-level fields.
    merged: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if key == "extra" and isinstance(value, dict):
            merged.update(value)
        else:
            merged[key] = value

    out: Dict[str, Any] = {}
    for key, value in merged.items():
        if value is None:
            continue
        out[f"ctx_{key}" if key in RESERVED_ATTRS else key] = value
    return out


def extract_extra(record: logging.LogRecord) -> Dict[str, Any]:
    """Return only the fields a caller attached, for human-readable rendering."""
    return {
        k: v
        for k, v in record.__dict__.items()
        if k not in RESERVED_ATTRS and not k.startswith("_")
    }


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
        try:
            # Get color for log level
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]

            # Format timestamp - handle Python shutdown gracefully
            try:
                timestamp = datetime.fromtimestamp(record.created).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ImportError, AttributeError):
                # Handle Python shutdown where sys.meta_path is None
                timestamp = "SHUTDOWN"

            # Format the message. Caller fields are appended here rather than
            # baked into the message at the call site, so the same record can be
            # human-readable here and fully structured over OTLP.
            fields = extract_extra(record)
            suffix = ""
            if fields:
                suffix = " " + " ".join(
                    f'{k}="{v}"' if isinstance(v, str) and " " in v else f"{k}={v}"
                    for k, v in fields.items()
                )
            formatted = f"{color}[{timestamp}] {record.levelname:8s} {record.name}: {record.getMessage()}{suffix}{reset}"

            # Add exception info if present
            if record.exc_info:
                formatted += f"\n{self.formatException(record.exc_info)}"

            return formatted
        except Exception:
            # Fallback to basic formatting during shutdown
            return f"[SHUTDOWN] {record.levelname}: {record.getMessage()}"


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
