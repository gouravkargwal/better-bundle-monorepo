"""
Development settings for BetterBundle Admin Dashboard
"""

import os
from decouple import config, Config, RepositoryEnv

# Load environment variables from .env.dev file
env_file = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", ".env.dev"
)
config = Config(RepositoryEnv(env_file))

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
        "HOST": "localhost",
        "PORT": "5432",
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
