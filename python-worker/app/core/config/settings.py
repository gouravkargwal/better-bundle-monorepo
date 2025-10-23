"""
Application settings and configuration management
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings

from app.shared.constants.app import (
    PROJECT_NAME,
    VERSION,
    DEFAULT_PORT,
    HEALTH_CHECK_TIMEOUT,
    ENVIRONMENT_DEVELOPMENT,
    DEFAULT_WORKER_ID,
    DEFAULT_WORKER_CONCURRENCY,
    DEFAULT_BATCH_SIZE,
    DEFAULT_POLLING_INTERVAL_MS,
    DEFAULT_IDLE_SLEEP_SECONDS,
    DEFAULT_ERROR_SLEEP_SECONDS,
)
from app.shared.constants.redis import (
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_TLS,
)
from app.core.exceptions import ConfigurationError, EnvironmentVariableError


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/betterbundle",
        env="DATABASE_URL",
    )
    # Control SQLAlchemy logging of SQL and pool events
    SQLALCHEMY_ECHO: bool = Field(default=False, env="SQLALCHEMY_ECHO")
    SQLALCHEMY_ECHO_POOL: bool = Field(default=False, env="SQLALCHEMY_ECHO_POOL")

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v:
            return "postgresql+asyncpg://postgres:postgres@postgres:5432/betterbundle"
        return v


class RedisSettings(BaseSettings):
    """Redis configuration settings"""

    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=DEFAULT_REDIS_PORT, env="REDIS_PORT")
    REDIS_PASSWORD: str = Field(default="", env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=DEFAULT_REDIS_DB, env="REDIS_DB")
    REDIS_TLS: bool = Field(default=DEFAULT_REDIS_TLS, env="REDIS_TLS")

    @validator("REDIS_HOST")
    def validate_redis_host(cls, v):
        if not v:
            return "localhost"
        return v

    @validator("REDIS_PASSWORD")
    def validate_redis_password(cls, v):
        if not v:
            return ""
        return v


class ShopifySettings(BaseSettings):
    """Shopify configuration settings"""

    SHOPIFY_APP_URL: str = Field(default="http://localhost:3000", env="SHOPIFY_APP_URL")
    SHOPIFY_ACCESS_TOKEN: str = Field(default="", env="SHOPIFY_ACCESS_TOKEN")

    # App Identity Configuration
    # Note: SHOPIFY_APP_ID is the GraphQL app ID (gid://shopify/App/...), not the client_id from shopify.app.toml
    SHOPIFY_APP_ID: str = Field(
        default="gid://shopify/App/277451505665", env="SHOPIFY_APP_ID"
    )
    SHOPIFY_APP_TITLE: str = Field(default="BetterBundle", env="SHOPIFY_APP_TITLE")

    # API Configuration
    SHOPIFY_API_RATE_LIMIT: int = Field(default=40, env="SHOPIFY_API_RATE_LIMIT")
    SHOPIFY_API_BATCH_SIZE: int = Field(default=250, env="SHOPIFY_API_BATCH_SIZE")

    # Data Collection
    MAX_INITIAL_DAYS: int = Field(default=60, env="MAX_INITIAL_DAYS")
    MAX_INCREMENTAL_DAYS: int = Field(default=30, env="MAX_INCREMENTAL_DAYS")
    FALLBACK_DAYS: int = Field(default=30, env="FALLBACK_DAYS")


class MLSettings(BaseSettings):
    """Machine Learning configuration settings"""

    # Gorse Integration
    ENABLE_GORSE_SYNC: bool = Field(default=False, env="ENABLE_GORSE_SYNC")
    GORSE_BASE_URL: str = Field(default="http://localhost:8088", env="GORSE_BASE_URL")
    GORSE_API_KEY: str = Field(default="", env="GORSE_API_KEY")
    GORSE_MASTER_KEY: str = Field(default="", env="GORSE_MASTER_KEY")

    # Training Configuration
    MIN_ORDERS_FOR_TRAINING: int = Field(default=1, env="MIN_ORDERS_FOR_TRAINING")
    MIN_PRODUCTS_FOR_TRAINING: int = Field(default=20, env="MIN_PRODUCTS_FOR_TRAINING")
    MAX_RECOMMENDATIONS: int = Field(default=10, env="MAX_RECOMMENDATIONS")
    MIN_CONFIDENCE_THRESHOLD: float = Field(default=0.3, env="MIN_CONFIDENCE_THRESHOLD")

    # Feature Computation
    TRANSFORM_FALLBACK_DAYS: int = Field(default=90, env="TRANSFORM_FALLBACK_DAYS")
    PRICE_TIER_LOW_MAX: float = Field(default=20.0, env="PRICE_TIER_LOW_MAX")
    PRICE_TIER_HIGH_MIN: float = Field(default=100.0, env="PRICE_TIER_HIGH_MIN")
    TIME_DECAY_LAMBDA: float = Field(default=0.07, env="TIME_DECAY_LAMBDA")


class WorkerSettings(BaseSettings):
    """Worker configuration settings"""

    WORKER_ID: str = Field(default=DEFAULT_WORKER_ID, env="WORKER_ID")
    WORKER_CONCURRENCY: int = Field(
        default=DEFAULT_WORKER_CONCURRENCY, env="WORKER_CONCURRENCY"
    )

    # Consumer Configuration
    ENABLE_FEATURES_CONSUMER: bool = Field(default=True, env="ENABLE_FEATURES_CONSUMER")
    ENABLE_ML_TRAINING_CONSUMER: bool = Field(
        default=True, env="ENABLE_ML_TRAINING_CONSUMER"
    )
    ENABLE_COMPLETION_HANDLER: bool = Field(
        default=True, env="ENABLE_COMPLETION_HANDLER"
    )
    ENABLE_HEURISTIC_DECISION_CONSUMER: bool = Field(
        default=True, env="ENABLE_HEURISTIC_DECISION_CONSUMER"
    )

    # Resource Optimization
    CONSUMER_POLLING_INTERVAL_MS: int = Field(
        default=DEFAULT_POLLING_INTERVAL_MS, env="CONSUMER_POLLING_INTERVAL_MS"
    )
    CONSUMER_BATCH_SIZE: int = Field(
        default=DEFAULT_BATCH_SIZE, env="CONSUMER_BATCH_SIZE"
    )
    CONSUMER_IDLE_SLEEP_SECONDS: int = Field(
        default=DEFAULT_IDLE_SLEEP_SECONDS, env="CONSUMER_IDLE_SLEEP_SECONDS"
    )
    CONSUMER_ERROR_SLEEP_SECONDS: int = Field(
        default=DEFAULT_ERROR_SLEEP_SECONDS, env="CONSUMER_ERROR_SLEEP_SECONDS"
    )

    # Redis Timeout Settings
    REDIS_TIMEOUT_BUFFER_SECONDS: int = Field(
        default=60,
        env="REDIS_TIMEOUT_BUFFER_SECONDS",  # Increased from 30 to 60 for better database reliability
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""

    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="console", env="LOG_FORMAT")

    # Grafana Loki settings
    GF_SECURITY_ENABLED: bool = Field(default=False, env="GF_SECURITY_ENABLED")
    GF_SECURITY_URL: str = Field(default="http://loki:3100", env="GF_SECURITY_URL")
    GF_SECURITY_ADMIN_USER: str = Field(default="admin", env="GF_SECURITY_ADMIN_USER")
    GF_SECURITY_ADMIN_PASSWORD: str = Field(
        default="admin", env="GF_SECURITY_ADMIN_PASSWORD"
    )

    # Comprehensive Logging Configuration
    LOGGING: dict = Field(
        default={
            "level": "INFO",
            "file": {
                "enabled": True,
                "log_dir": "logs",
                "max_file_size": 10485760,  # 10MB
                "backup_count": 5,
                "app_log_enabled": True,
                "error_log_enabled": True,
                "consumer_log_enabled": True,
            },
            "console": {
                "enabled": True,
                "level": "INFO",
            },
            "prometheus": {
                "enabled": True,
            },
            "grafana": {
                "enabled": False,
                "url": "http://loki:3100",
                "username": "admin",
                "password": "admin",
                "service_name": "betterbundle-python-worker",
                "labels": {
                    "service": "betterbundle-python-worker",
                    "env": "development",
                },
            },
            "telemetry": {
                "enabled": False,
                "endpoint": "",
                "service_name": "betterbundle-python-worker",
            },
            "gcp": {
                "enabled": False,
                "project_id": "",
                "log_name": "betterbundle-python-worker",
            },
            "aws": {
                "enabled": False,
                "region": "",
                "log_group": "betterbundle-python-worker",
                "log_stream": "",
            },
        },
        env="LOGGING",
    )

    def model_post_init(self, __context):
        """Update logging config with environment variables after initialization"""
        self.LOGGING["grafana"]["enabled"] = self.GF_SECURITY_ENABLED
        self.LOGGING["grafana"]["url"] = self.GF_SECURITY_URL
        self.LOGGING["grafana"]["username"] = self.GF_SECURITY_ADMIN_USER
        self.LOGGING["grafana"]["password"] = self.GF_SECURITY_ADMIN_PASSWORD


class Settings(BaseSettings):
    """Main application settings"""

    # App Configuration
    PROJECT_NAME: str = PROJECT_NAME
    VERSION: str = VERSION
    DEBUG: bool = Field(default=False, env="DEBUG")
    PORT: int = Field(default=DEFAULT_PORT, env="PORT")
    ENVIRONMENT: str = Field(default=ENVIRONMENT_DEVELOPMENT, env="ENVIRONMENT")

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    shopify: ShopifySettings = ShopifySettings()
    ml: MLSettings = MLSettings()
    worker: WorkerSettings = WorkerSettings()
    logging: LoggingSettings = LoggingSettings()

    # External Services
    ML_API_URL: str = Field(default="http://localhost:8000", env="ML_API_URL")

    # Redis Configuration (Direct access for backward compatibility)
    @property
    def REDIS_HOST(self) -> str:
        return self.redis.REDIS_HOST

    @property
    def REDIS_PORT(self) -> int:
        return self.redis.REDIS_PORT

    @property
    def REDIS_PASSWORD(self) -> str:
        return self.redis.REDIS_PASSWORD

    @property
    def REDIS_DB(self) -> int:
        return self.redis.REDIS_DB

    @property
    def REDIS_TLS(self) -> bool:
        return self.redis.REDIS_TLS

    # Redis Stream Names (Direct access for backward compatibility)
    @property
    def ML_TRAINING_STREAM(self) -> str:
        return self.redis.ML_TRAINING_STREAM

    @property
    def ANALYSIS_RESULTS_STREAM(self) -> str:
        return self.redis.ANALYSIS_RESULTS_STREAM

    @property
    def USER_NOTIFICATIONS_STREAM(self) -> str:
        return self.redis.USER_NOTIFICATIONS_STREAM

    @property
    def FEATURES_COMPUTED_STREAM(self) -> str:
        return self.redis.FEATURES_COMPUTED_STREAM

    @property
    def ML_TRAINING_COMPLETE_STREAM(self) -> str:
        return self.redis.ML_TRAINING_COMPLETE_STREAM

    @property
    def HEURISTIC_DECISION_REQUESTED_STREAM(self) -> str:
        return self.redis.HEURISTIC_DECISION_REQUESTED_STREAM

    @property
    def HEURISTIC_DECISION_MADE_STREAM(self) -> str:
        return self.redis.HEURISTIC_DECISION_MADE_STREAM

    @property
    def HEURISTIC_DECISION_STREAM(self) -> str:
        return self.redis.HEURISTIC_DECISION_STREAM

    @property
    def NEXT_ANALYSIS_SCHEDULED_STREAM(self) -> str:
        return self.redis.NEXT_ANALYSIS_SCHEDULED_STREAM

    @property
    def COMPLETION_RESULTS_STREAM(self) -> str:
        return self.redis.COMPLETION_RESULTS_STREAM

    @property
    def COMPLETION_EVENTS_STREAM(self) -> str:
        return self.redis.COMPLETION_EVENTS_STREAM

    @property
    def BEHAVIORAL_EVENTS_STREAM(self) -> str:
        return self.redis.BEHAVIORAL_EVENTS_STREAM

    @property
    def GORSE_SYNC_STREAM(self) -> str:
        return self.redis.GORSE_SYNC_STREAM

    # Worker Configuration (Direct access for backward compatibility)
    @property
    def WORKER_ID(self) -> str:
        return self.worker.WORKER_ID

    @property
    def REDIS_TIMEOUT_BUFFER_SECONDS(self) -> int:
        return self.worker.REDIS_TIMEOUT_BUFFER_SECONDS

    # Retry Configuration
    MAX_RETRIES: int = Field(default=5, env="MAX_RETRIES")  # Increased from 3 to 5
    RETRY_DELAY: float = Field(
        default=2.0, env="RETRY_DELAY"
    )  # Increased from 1.0 to 2.0
    RETRY_BACKOFF: float = Field(default=2.0, env="RETRY_BACKOFF")

    # Database Timeout Configuration - Industry Standard
    DATABASE_CONNECT_TIMEOUT: int = Field(
        default=10, env="DATABASE_CONNECT_TIMEOUT"
    )  # Reduced from 30
    DATABASE_QUERY_TIMEOUT: int = Field(
        default=30, env="DATABASE_QUERY_TIMEOUT"
    )  # Reduced from 60
    DATABASE_POOL_TIMEOUT: int = Field(
        default=10, env="DATABASE_POOL_TIMEOUT"
    )  # Reduced from 30
    DATABASE_HEALTH_CHECK_INTERVAL: int = Field(
        default=300, env="DATABASE_HEALTH_CHECK_INTERVAL"
    )  # 5 minutes

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=HEALTH_CHECK_TIMEOUT, env="HEALTH_CHECK_TIMEOUT"
    )

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # SendPulse Email Configuration
    SENDPULSE_USER_ID: str = Field(default="", env="SENDPULSE_USER_ID")
    SENDPULSE_SECRET: str = Field(default="", env="SENDPULSE_SECRET")
    SENDPULSE_SENDER_EMAIL: str = Field(
        default="noreply@betterbundle.com", env="SENDPULSE_SENDER_EMAIL"
    )
    SENDPULSE_SENDER_NAME: str = Field(
        default="BetterBundle", env="SENDPULSE_SENDER_NAME"
    )

    class Config:
        env_file = [".env.local", ".env"]  # Try .env.local first, then .env
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"

    def validate_configuration(self) -> None:
        """Validate the complete configuration"""
        try:
            # For development, we'll use defaults if not provided
            # In production, these should be properly configured
            pass

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Configuration validation failed: {str(e)}")


# Create settings instance
settings = Settings()

# Validate configuration on import
try:
    settings.validate_configuration()
except ConfigurationError as e:
    print(f"Configuration Error: {e}")
    raise
