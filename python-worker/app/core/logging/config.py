"""
Logging configuration for BetterBundle Python Worker
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


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


@dataclass
class PrometheusHandlerConfig:
    """Prometheus handler configuration"""

    enabled: bool = True
    port: int = 9090
    metrics_path: str = "/metrics"


@dataclass
class GrafanaConfig:
    """Grafana configuration"""

    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""


@dataclass
class TelemetryConfig:
    """Telemetry configuration"""

    enabled: bool = False
    endpoint: str = ""
    service_name: str = "betterbundle-python-worker"


@dataclass
class GCPConfig:
    """Google Cloud Platform logging configuration"""

    enabled: bool = False
    project_id: str = ""
    log_name: str = "betterbundle-python-worker"


@dataclass
class AWSConfig:
    """AWS CloudWatch logging configuration"""

    enabled: bool = False
    region: str = ""
    log_group: str = "betterbundle-python-worker"
    log_stream: str = ""


class LoggingConfig(BaseModel):
    """Complete logging configuration"""

    level: str = "INFO"
    format: str = "console"  # json or console

    # Handler configurations
    file: FileHandlerConfig = FileHandlerConfig()
    console: ConsoleHandlerConfig = ConsoleHandlerConfig()
    prometheus: PrometheusHandlerConfig = PrometheusHandlerConfig()

    # External logging services
    grafana: GrafanaConfig = GrafanaConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    gcp: GCPConfig = GCPConfig()
    aws: AWSConfig = AWSConfig()

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
            "prometheus": {
                "enabled": self.prometheus.enabled,
                "port": self.prometheus.port,
                "metrics_path": self.prometheus.metrics_path,
            },
            "grafana": {
                "enabled": self.grafana.enabled,
                "url": self.grafana.url,
                "username": self.grafana.username,
                "password": self.grafana.password,
            },
            "telemetry": {
                "enabled": self.telemetry.enabled,
                "endpoint": self.telemetry.endpoint,
                "service_name": self.telemetry.service_name,
            },
            "gcp": {
                "enabled": self.gcp.enabled,
                "project_id": self.gcp.project_id,
                "log_name": self.gcp.log_name,
            },
            "aws": {
                "enabled": self.aws.enabled,
                "region": self.aws.region,
                "log_group": self.aws.log_group,
                "log_stream": self.aws.log_stream,
            },
        }
