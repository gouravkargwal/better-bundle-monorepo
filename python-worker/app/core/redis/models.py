"""
Redis models and configuration classes
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


@dataclass
class RedisConnectionConfig:
    """Redis connection configuration"""

    host: str
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    tls: bool = False
    decode_responses: bool = True
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0
    socket_keepalive: bool = True
    retry_on_timeout: bool = True
    health_check_interval: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "host": self.host,
            "port": self.port,
            "password": self.password,
            "db": self.db,
            "tls": self.tls,
            "decode_responses": self.decode_responses,
            "socket_connect_timeout": self.socket_connect_timeout,
            "socket_timeout": self.socket_timeout,
            "socket_keepalive": self.socket_keepalive,
            "retry_on_timeout": self.retry_on_timeout,
            "health_check_interval": self.health_check_interval,
        }


class RedisStreamConfig(BaseModel):
    """Redis stream configuration"""

    stream_name: str
    max_len: int = 1000
    approx_max_len: bool = True
    idle_time: int = 300000  # 5 minutes in milliseconds
    consumer_group: str
    consumer_name: str

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}


class RedisHealthStatus(BaseModel):
    """Redis health status"""

    is_healthy: bool
    connection_info: Dict[str, Any]
    last_check: str
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}


class RedisMetrics(BaseModel):
    """Redis performance metrics"""

    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_response_time_ms: float = 0.0
    slow_operations_count: int = 0
    connection_errors: int = 0
    stream_operations: int = 0
    last_reset: str

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}


class StreamEvent(BaseModel):
    """Redis stream event"""

    stream_name: str
    event_id: str
    event_data: Dict[str, Any]
    timestamp: str
    consumer_group: Optional[str] = None
    consumer_name: Optional[str] = None

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}
