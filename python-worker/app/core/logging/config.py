"""
Logging configuration for BetterBundle Python Worker
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from .otel_logger import init_otel_logger


@dataclass
class FileHandlerConfig:
    """File handler configuration"""

    enabled: bool = True
    log_dir: str = "logs"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    app_log_enabled: bool = True
    error_log_enabled: bool = True
    consumer_log_enabled: bool = True


@dataclass
class ConsoleHandlerConfig:
    """Console handler configuration"""

    enabled: bool = True
    level: str = "INFO"


class LoggingConfig(BaseModel):
    """Complete logging configuration"""

    level: str = "INFO"
    format: str = "console"  # json or console

    # Handler configurations
    file: FileHandlerConfig = FileHandlerConfig()
    console: ConsoleHandlerConfig = ConsoleHandlerConfig()

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "level": self.level,
            "format": self.format,
            "file": {
                "enabled": self.file.enabled,
                "log_dir": self.file.log_dir,
                "max_file_size": self.file.max_file_size,
                "backup_count": self.file.backup_count,
                "app_log_enabled": self.file.app_log_enabled,
                "error_log_enabled": self.file.error_log_enabled,
                "consumer_log_enabled": self.file.consumer_log_enabled,
            },
            "console": {
                "enabled": self.console.enabled,
                "level": self.console.level,
            },
        }


def initialize_otel_logging(settings: "Settings") -> "LoggerProvider":
    """Initialize OpenTelemetry logging for the application.

    Delegates to :func:`init_otel_logger` from :mod:`otel_logger`.
    Called during app startup to wire up the OTLP log exporter.
    """
    return init_otel_logger(settings)
