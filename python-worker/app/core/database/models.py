"""
Database models and configuration classes
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pydantic import BaseModel


@dataclass
class DatabaseConnectionConfig:
    """Database connection configuration"""

    url: str
    max_connections: int = 10
    min_connections: int = 1
    connection_timeout: float = 30.0
    command_timeout: float = 30.0
    pool_timeout: float = 30.0
    max_lifetime: float = 3600.0  # 1 hour
    idle_timeout: float = 300.0  # 5 minutes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "url": self.url,
            "max_connections": self.max_connections,
            "min_connections": self.min_connections,
            "connection_timeout": self.connection_timeout,
            "command_timeout": self.command_timeout,
            "pool_timeout": self.pool_timeout,
            "max_lifetime": self.max_lifetime,
            "idle_timeout": self.idle_timeout,
        }


class DatabaseHealthStatus(BaseModel):
    """Database health status"""

    is_healthy: bool
    connection_count: int
    last_check: str
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}


class DatabaseMetrics(BaseModel):
    """Database performance metrics"""

    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_response_time_ms: float = 0.0
    slow_queries_count: int = 0
    connection_errors: int = 0
    last_reset: str

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}
