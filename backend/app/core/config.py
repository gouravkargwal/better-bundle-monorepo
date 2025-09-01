"""
Core configuration for the ML API
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from local.env
env_path = Path(__file__).parent.parent.parent.parent / "local.env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "BetterBundle ML API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Configuration
    DATABASE_URL: str = "postgresql://localhost:5432/betterbundle"

    # ML Configuration
    SIMILARITY_TEXT_WEIGHT: float = 0.7
    SIMILARITY_NUMERICAL_WEIGHT: float = 0.3
    SIMILARITY_MAX_FEATURES: int = 1000
    SIMILARITY_MIN_THRESHOLD: float = 0.1
    SIMILARITY_TOP_K: int = 10

    # Bundle Configuration
    BUNDLE_MIN_SUPPORT: float = 0.01
    BUNDLE_MIN_CONFIDENCE: float = 0.3
    BUNDLE_MIN_LIFT: float = 1.2
    BUNDLE_MAX_SIZE: int = 2

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # CORS Configuration
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    class Config:
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment


# Global settings instance
settings = Settings()
