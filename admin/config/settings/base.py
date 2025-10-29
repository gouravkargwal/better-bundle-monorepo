"""
Base settings for BetterBundle Admin Dashboard
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "django_tables2",
    "django_filters",
    "import_export",
    "django_extensions",
]

LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.shops.apps.ShopsConfig",
    "apps.billing.apps.BillingConfig",
    "apps.revenue.apps.RevenueConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

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

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Authentication
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Django Tables2
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"

# Admin Settings
ADMIN_SITE_HEADER = "BetterBundle Admin"
ADMIN_SITE_TITLE = "BetterBundle Admin Portal"
ADMIN_INDEX_TITLE = "Welcome to BetterBundle Administration"

# Server Settings
PORT = config("PORT", default=8000, cast=int)
HOST = config("HOST", default="0.0.0.0")


# Database Migration Settings
# IMPORTANT: Django should NOT create business tables - they already exist from Python worker
# But allow Django's own auth tables to be created
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        # Allow Django's built-in apps to have migrations
        if item in ["auth", "contenttypes", "sessions", "admin"]:
            return None
        # Disable migrations for business apps
        return None


MIGRATION_MODULES = DisableMigrations()


# CRITICAL: Prevent Django from creating business tables
# This ensures Django only reads from existing tables created by Python worker
# But allows Django's own auth tables to be created
class NoCreateTablesRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Allow Django's built-in auth tables to be created
        if app_label in [
            "auth",
            "contenttypes",
            "sessions",
            "admin",
            "django_admin_log",
        ]:
            return True
        # Block all business apps from creating tables
        if app_label in ["shops", "billing", "revenue", "core"]:
            return False
        # Allow other Django system tables
        return True


DATABASE_ROUTERS = [NoCreateTablesRouter()]

# Ensure Django doesn't try to create tables
DATABASE_APPS_MAPPING = {
    "shops": "default",
    "billing": "default",
    "revenue": "default",
    "core": "default",
}

# Python Worker API Configuration
PYTHON_WORKER_API_URL = config("PYTHON_WORKER_API_URL", default="http://localhost:8001")
