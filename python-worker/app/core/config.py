"""
Configuration settings for the Python Worker
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""

    # App Configuration
    PROJECT_NAME: str = "BetterBundle Python Worker"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    PORT: int = Field(default=8001, env="PORT")

    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")

    # Database Configuration
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    # Redis Configuration (Upstash)
    REDIS_HOST: str = Field(..., env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: str = Field(..., env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_TLS: bool = Field(default=True, env="REDIS_TLS")

    # Redis Stream Names
    DATA_JOB_STREAM: str = Field(
        default="betterbundle:data-jobs", env="DATA_JOB_STREAM"
    )
    ML_TRAINING_STREAM: str = Field(
        default="betterbundle:ml-training", env="ML_TRAINING_STREAM"
    )
    ANALYSIS_RESULTS_STREAM: str = Field(
        default="betterbundle:analysis-results", env="ANALYSIS_RESULTS_STREAM"
    )
    USER_NOTIFICATIONS_STREAM: str = Field(
        default="betterbundle:user-notifications", env="USER_NOTIFICATIONS_STREAM"
    )
    FEATURES_COMPUTED_STREAM: str = Field(
        default="betterbundle:features-computed", env="FEATURES_COMPUTED_STREAM"
    )
    ML_TRAINING_COMPLETE_STREAM: str = Field(
        default="betterbundle:ml-training-complete", env="ML_TRAINING_COMPLETE_STREAM"
    )

    # Consumer Group Names
    DATA_PROCESSOR_GROUP: str = Field(
        default="data-processors", env="DATA_PROCESSOR_GROUP"
    )

    # External Services
    ML_API_URL: str = Field(default="http://localhost:8000", env="ML_API_URL")
    SHOPIFY_APP_URL: str = Field(default="http://localhost:3000", env="SHOPIFY_APP_URL")
    SHOPIFY_ACCESS_TOKEN: str = Field(default="", env="SHOPIFY_ACCESS_TOKEN")

    # Data Collection Configuration
    MAX_INITIAL_DAYS: int = Field(default=60, env="MAX_INITIAL_DAYS")
    MAX_INCREMENTAL_DAYS: int = Field(default=30, env="MAX_INCREMENTAL_DAYS")
    FALLBACK_DAYS: int = Field(default=30, env="FALLBACK_DAYS")

    # Transformation Configuration
    TRANSFORM_FALLBACK_DAYS: int = Field(default=90, env="TRANSFORM_FALLBACK_DAYS")
    PRICE_TIER_LOW_MAX: float = Field(default=20.0, env="PRICE_TIER_LOW_MAX")
    PRICE_TIER_HIGH_MIN: float = Field(default=100.0, env="PRICE_TIER_HIGH_MIN")
    TIME_DECAY_LAMBDA: float = Field(default=0.07, env="TIME_DECAY_LAMBDA")

    # Rate Limiting
    SHOPIFY_API_RATE_LIMIT: int = Field(
        default=40, env="SHOPIFY_API_RATE_LIMIT"
    )  # requests per second
    SHOPIFY_API_BATCH_SIZE: int = Field(default=250, env="SHOPIFY_API_BATCH_SIZE")

    # Retry Configuration
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    RETRY_DELAY: float = Field(default=1.0, env="RETRY_DELAY")  # seconds
    RETRY_BACKOFF: float = Field(
        default=2.0, env="RETRY_BACKOFF"
    )  # exponential backoff multiplier

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = Field(default=5, env="HEALTH_CHECK_TIMEOUT")  # seconds

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://*.vercel.app"], env="CORS_ORIGINS"
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")  # json or console

    # Worker Configuration
    WORKER_ID: str = Field(default="python-worker-1", env="WORKER_ID")
    WORKER_CONCURRENCY: int = Field(default=4, env="WORKER_CONCURRENCY")

    # Gorse Integration (optional)
    ENABLE_GORSE_SYNC: bool = Field(default=False, env="ENABLE_GORSE_SYNC")
    GORSE_BASE_URL: str = Field(default="http://localhost:8088", env="GORSE_BASE_URL")
    GORSE_API_KEY: str = Field(default="", env="GORSE_API_KEY")
    GORSE_MASTER_KEY: str = Field(default="", env="GORSE_MASTER_KEY")

    # Training Configuration
    MIN_ORDERS_FOR_TRAINING: int = Field(default=50, env="MIN_ORDERS_FOR_TRAINING")
    MIN_PRODUCTS_FOR_TRAINING: int = Field(default=20, env="MIN_PRODUCTS_FOR_TRAINING")
    MAX_RECOMMENDATIONS: int = Field(default=10, env="MAX_RECOMMENDATIONS")
    MIN_CONFIDENCE_THRESHOLD: float = Field(default=0.3, env="MIN_CONFIDENCE_THRESHOLD")

    # SendPulse Email Configuration
    SENDPULSE_USER_ID: str = os.getenv("SENDPULSE_USER_ID", "")
    SENDPULSE_SECRET: str = os.getenv("SENDPULSE_SECRET", "")
    SENDPULSE_SENDER_EMAIL: str = os.getenv(
        "SENDPULSE_SENDER_EMAIL", "noreply@betterbundle.com"
    )
    SENDPULSE_SENDER_NAME: str = os.getenv("SENDPULSE_SENDER_NAME", "BetterBundle")

    class Config:
        env_file = ".env"
        extra = "allow"


# Create settings instance
settings = Settings()
