"""
Development settings for BetterBundle Admin Dashboard
"""

import os
from decouple import config as decouple_config, Config, RepositoryEnv

# Load environment variables from .env.dev file.
# docker-compose passes these via env_file, so this is a fallback for local dev.
env_file = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", ".env.dev"
)
if os.path.exists(env_file):
    config = Config(RepositoryEnv(env_file))
else:
    # Fall back to OS environment (set by docker-compose env_file)
    config = decouple_config

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="betterbundle"),
        "USER": config("POSTGRES_USER", default="postgres"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Server Settings
PORT = config("PORT", default=8001, cast=int)
HOST = config("HOST", default="127.0.0.1")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
