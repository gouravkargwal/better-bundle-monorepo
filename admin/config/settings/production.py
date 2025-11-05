"""
Production settings for BetterBundle Admin Dashboard
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Ensure production domain is in ALLOWED_HOSTS
# ALLOWED_HOSTS is already set in base.py from config, but we need to ensure production domain is included
if "admin.betterbundle.site" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("admin.betterbundle.site")

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CSRF settings
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
# CSRF trusted origins for production
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="https://admin.betterbundle.site"
).split(",")

# Database: use base defaults (POSTGRES_*), allow optional DB_* overrides if provided
DATABASES["default"]["NAME"] = config("DB_NAME", default=DATABASES["default"]["NAME"])
DATABASES["default"]["USER"] = config("DB_USER", default=DATABASES["default"]["USER"])
DATABASES["default"]["PASSWORD"] = config(
    "DB_PASSWORD", default=DATABASES["default"]["PASSWORD"]
)
DATABASES["default"]["HOST"] = config("DB_HOST", default=DATABASES["default"]["HOST"])
DATABASES["default"]["PORT"] = config("DB_PORT", default=DATABASES["default"]["PORT"])
# PostgreSQL default transaction isolation is already "read committed"
# No need to set it explicitly

# Server Settings
PORT = config("PORT", default=8000, cast=int)
HOST = config("HOST", default="0.0.0.0")

# Email settings (optional). Defaults to console backend if SMTP envs are absent.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "/var/log/betterbundle-admin/django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO",
    },
}
