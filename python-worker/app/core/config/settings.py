"""
Application settings and configuration management
"""

from typing import List
from pydantic import Field, validator
from pydantic_settings import BaseSettings

from app.shared.constants.app import (
    PROJECT_NAME,
    VERSION,
    DEFAULT_PORT,
    HEALTH_CHECK_TIMEOUT,
    ENVIRONMENT_DEVELOPMENT,
    ENVIRONMENT_PRODUCTION,
)
from app.shared.constants.redis import (
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_TLS,
)
from app.core.exceptions import ConfigurationError


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""

    DATABASE_URL: str = Field(default="", env="DATABASE_URL")
    # Control SQLAlchemy logging of SQL and pool events
    SQLALCHEMY_ECHO: bool = Field(default=False, env="SQLALCHEMY_ECHO")
    SQLALCHEMY_ECHO_POOL: bool = Field(default=False, env="SQLALCHEMY_ECHO_POOL")

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v:
            raise ValueError(
                "DATABASE_URL is required. Set it in your environment or .env file."
            )
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

    # API Configuration
    SHOPIFY_API_RATE_LIMIT: int = Field(default=40, env="SHOPIFY_API_RATE_LIMIT")
    SHOPIFY_API_BATCH_SIZE: int = Field(default=250, env="SHOPIFY_API_BATCH_SIZE")
    SHOPIFY_API_VERSION: str = Field(default="2026-07", env="SHOPIFY_API_VERSION")

    # Data Collection
    MAX_INITIAL_DAYS: int = Field(default=60, env="MAX_INITIAL_DAYS")
    MAX_INCREMENTAL_DAYS: int = Field(default=30, env="MAX_INCREMENTAL_DAYS")
    FALLBACK_DAYS: int = Field(default=30, env="FALLBACK_DAYS")


class MLSettings(BaseSettings):
    """Machine Learning / AI configuration settings"""

    # Provider selection: "gemini" (AI Studio) or "vertex" (Vertex AI)
    AI_PROVIDER: str = Field(default="gemini", env="AI_PROVIDER")

    # Gemini / AI Studio
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")

    # Vertex AI
    VERTEX_PROJECT_ID: str = Field(default="", env="VERTEX_PROJECT_ID")
    VERTEX_LOCATION: str = Field(default="us-central1", env="VERTEX_LOCATION")

    # Chat / enrichment model
    AI_CHAT_MODEL: str = Field(default="gemini-2.5-flash-lite", env="AI_CHAT_MODEL")


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""

    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="console", env="LOG_FORMAT")

    # Fraction of DEBUG/INFO records shipped to OpenObserve. Unset means
    # environment-derived: 10% in production, 100% elsewhere (see
    # app.core.logging.sampling.rate_for). WARNING and above are never sampled.
    LOG_SAMPLE_RATE: float | None = Field(default=None, env="LOG_SAMPLE_RATE")

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

    # Security Configuration
    SECRET_KEY: str = Field(default="", env="SECRET_KEY")

    # Admin / operations console
    ADMIN_CRON_SECRET: str = Field(default="", env="ADMIN_CRON_SECRET")
    ADMIN_USERNAME: str = Field(default="admin", env="ADMIN_USERNAME")
    ADMIN_PASSWORD: str = Field(default="", env="ADMIN_PASSWORD")
    ADMIN_SECRET_KEY: str = Field(default="", env="ADMIN_SECRET_KEY")

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    shopify: ShopifySettings = ShopifySettings()
    ml: MLSettings = MLSettings()
    logging: LoggingSettings = LoggingSettings()

    # OpenObserve (new observability platform)
    OPENOBSERVE_ENDPOINT: str = Field(
        default="http://localhost:5080", env="OPENOBSERVE_ENDPOINT"
    )
    OPENOBSERVE_ORG: str = Field(default="default", env="OPENOBSERVE_ORG")
    OPENOBSERVE_API_KEY: str = Field(default="", env="OPENOBSERVE_API_KEY")

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

    # Retry Configuration
    MAX_RETRIES: int = Field(default=5, env="MAX_RETRIES")
    RETRY_DELAY: float = Field(default=2.0, env="RETRY_DELAY")
    RETRY_BACKOFF: float = Field(default=2.0, env="RETRY_BACKOFF")

    # Database Timeout Configuration
    DATABASE_CONNECT_TIMEOUT: int = Field(default=10, env="DATABASE_CONNECT_TIMEOUT")
    DATABASE_QUERY_TIMEOUT: int = Field(default=30, env="DATABASE_QUERY_TIMEOUT")
    DATABASE_POOL_TIMEOUT: int = Field(default=10, env="DATABASE_POOL_TIMEOUT")
    DATABASE_HEALTH_CHECK_INTERVAL: int = Field(
        default=300, env="DATABASE_HEALTH_CHECK_INTERVAL"
    )

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=HEALTH_CHECK_TIMEOUT, env="HEALTH_CHECK_TIMEOUT"
    )

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(default=[], env="CORS_ORIGINS")

    class Config:
        env_file = [".env.local", ".env"]
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"

    def validate_configuration(self) -> None:
        """Validate the complete configuration.

        In production, critical secrets and URLs must be explicitly set.
        Missing values raise ConfigurationError instead of silently falling
        back to hardcoded defaults.
        """
        try:
            if self.ENVIRONMENT == ENVIRONMENT_PRODUCTION:
                missing = []
                if not self.SECRET_KEY:
                    missing.append("SECRET_KEY")
                if not self.ADMIN_CRON_SECRET:
                    missing.append("ADMIN_CRON_SECRET")
                if not self.ADMIN_PASSWORD:
                    missing.append("ADMIN_PASSWORD")
                if not self.ADMIN_SECRET_KEY:
                    missing.append("ADMIN_SECRET_KEY")
                if missing:
                    raise ConfigurationError(
                        f"Missing required production configuration: {', '.join(missing)}"
                    )
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Configuration validation failed: {str(e)}")


# Create settings instance
settings = Settings()

# Validate configuration on import
try:
    settings.validate_configuration()
except ConfigurationError as e:
    print(f"Configuration Error: {e}")
    raise
