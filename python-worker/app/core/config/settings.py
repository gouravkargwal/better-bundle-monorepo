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
    DATA_JOB_STREAM,
    ML_TRAINING_STREAM,
    ANALYSIS_RESULTS_STREAM,
    USER_NOTIFICATIONS_STREAM,
    FEATURES_COMPUTED_STREAM,
    ML_TRAINING_COMPLETE_STREAM,
    HEURISTIC_DECISION_REQUESTED_STREAM,
    HEURISTIC_DECISION_MADE_STREAM,
    HEURISTIC_DECISION_STREAM,
    NEXT_ANALYSIS_SCHEDULED_STREAM,
    COMPLETION_RESULTS_STREAM,
    COMPLETION_EVENTS_STREAM,
    DATA_PROCESSOR_GROUP,
    FEATURES_CONSUMER_GROUP,
    ML_TRAINING_GROUP,
    HEURISTIC_DECISION_GROUP,
    COMPLETION_HANDLER_GROUP,
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_TLS,
)
from app.core.exceptions import ConfigurationError, EnvironmentVariableError


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""

    DATABASE_URL: str = Field(default="sqlite:///./betterbundle.db", env="DATABASE_URL")

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v:
            return "sqlite:///./betterbundle.db"
        return v


class RedisSettings(BaseSettings):
    """Redis configuration settings"""

    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=DEFAULT_REDIS_PORT, env="REDIS_PORT")
    REDIS_PASSWORD: str = Field(default="", env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=DEFAULT_REDIS_DB, env="REDIS_DB")
    REDIS_TLS: bool = Field(default=DEFAULT_REDIS_TLS, env="REDIS_TLS")

    # Redis Stream Names
    DATA_JOB_STREAM: str = Field(default=DATA_JOB_STREAM, env="DATA_JOB_STREAM")
    ML_TRAINING_STREAM: str = Field(
        default=ML_TRAINING_STREAM, env="ML_TRAINING_STREAM"
    )
    ANALYSIS_RESULTS_STREAM: str = Field(
        default=ANALYSIS_RESULTS_STREAM, env="ANALYSIS_RESULTS_STREAM"
    )
    USER_NOTIFICATIONS_STREAM: str = Field(
        default=USER_NOTIFICATIONS_STREAM, env="USER_NOTIFICATIONS_STREAM"
    )
    FEATURES_COMPUTED_STREAM: str = Field(
        default=FEATURES_COMPUTED_STREAM, env="FEATURES_COMPUTED_STREAM"
    )
    ML_TRAINING_COMPLETE_STREAM: str = Field(
        default=ML_TRAINING_COMPLETE_STREAM, env="ML_TRAINING_COMPLETE_STREAM"
    )

    # Consumer Group Names
    DATA_PROCESSOR_GROUP: str = Field(
        default=DATA_PROCESSOR_GROUP, env="DATA_PROCESSOR_GROUP"
    )
    FEATURES_CONSUMER_GROUP: str = Field(
        default=FEATURES_CONSUMER_GROUP, env="FEATURES_CONSUMER_GROUP"
    )
    ML_TRAINING_GROUP: str = Field(default=ML_TRAINING_GROUP, env="ML_TRAINING_GROUP")

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
    MIN_ORDERS_FOR_TRAINING: int = Field(default=50, env="MIN_ORDERS_FOR_TRAINING")
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
        default=30, env="REDIS_TIMEOUT_BUFFER_SECONDS"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""

    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")

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
                "url": "",
                "username": "",
                "password": "",
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
    def DATA_JOB_STREAM(self) -> str:
        return self.redis.DATA_JOB_STREAM

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

    # Worker Configuration (Direct access for backward compatibility)
    @property
    def WORKER_ID(self) -> str:
        return self.worker.WORKER_ID

    @property
    def REDIS_TIMEOUT_BUFFER_SECONDS(self) -> int:
        return self.worker.REDIS_TIMEOUT_BUFFER_SECONDS

    # Retry Configuration
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    RETRY_DELAY: float = Field(default=1.0, env="RETRY_DELAY")
    RETRY_BACKOFF: float = Field(default=2.0, env="RETRY_BACKOFF")

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=HEALTH_CHECK_TIMEOUT, env="HEALTH_CHECK_TIMEOUT"
    )

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://*.vercel.app"], env="CORS_ORIGINS"
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
        env_file = ".env"
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
