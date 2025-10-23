#!/usr/bin/env python3
"""
Local development server for BetterBundle Python Worker

This script is specifically designed to run the Python worker locally
with localhost configurations instead of Docker hostnames.

Usage:
    python run_local.py

Environment Variables:
    The script will load environment variables from .env.local file
    in the python-worker directory, or use localhost defaults.
"""

import os
import sys
import uvicorn
import logging
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def load_local_env():
    """Load environment variables from local .env.local file"""
    env_file = current_dir / ".env.local"

    if env_file.exists():
        print(f"📁 Loading environment from: {env_file}")
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key.strip()] = value
    else:
        print("⚠️  No .env.local file found, using default localhost configurations")
        # Create a sample .env.local file
        create_sample_env_file(env_file)


def create_sample_env_file(env_file):
    """Create a sample .env.local file with localhost configurations"""
    sample_content = """# ===========================================
# BetterBundle Python Worker - Local Development
# ===========================================

# ===========================================
# APPLICATION SETTINGS
# ===========================================
NODE_ENV=development
DEBUG=true
LOG_LEVEL=debug
HOT_RELOAD=true
PORT=8001

# ===========================================
# DATABASE CONFIGURATION
# ===========================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/betterbundle
POSTGRES_DB=betterbundle
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# ===========================================
# REDIS CONFIGURATION
# ===========================================
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ===========================================
# KAFKA CONFIGURATION
# ===========================================
KAFKA_BROKERS=localhost:9092
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# ===========================================
# GORSE RECOMMENDATION ENGINE
# ===========================================
GORSE_API_URL=http://localhost:8088
GORSE_API_KEY=secure_random_key_123
GORSE_LOG_LEVEL=debug

# ===========================================
# SHOPIFY APP CONFIGURATION (Development)
# ===========================================
SHOPIFY_APP_URL=https://poster-salaries-hispanic-overhead.trycloudflare.com
SCOPES=read_analytics,read_content,read_customers,read_discounts,read_inventory,read_locales,read_marketing_events,read_orders,read_price_rules,read_products,read_script_tags,read_themes,write_content,write_customers,write_discounts,write_inventory,write_locales,write_marketing_events,write_orders,write_price_rules,write_products,write_script_tags,write_themes
SHOPIFY_API_KEY=abc123def456ghi789jkl012mno345pqr678
SHOPIFY_API_SECRET=xyz789uvw456rst123def456ghi789jkl012mno345pqr678

# ===========================================
# MONITORING & LOGGING
# ===========================================
LOKI_URL=http://localhost:3100
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
GF_USERS_ALLOW_SIGN_UP=false
GF_SERVER_ROOT_URL=http://localhost:3001
GF_INSTALL_PLUGINS=redis-datasource

# ===========================================
# SECURITY & ENCRYPTION (Development)
# ===========================================
JWT_SECRET=dev_jwt_secret_123
ENCRYPTION_KEY=dev_encryption_key_123
"""

    with open(env_file, "w") as f:
        f.write(sample_content)
    print(f"📝 Created sample .env.local file at: {env_file}")
    print("   You can modify this file to customize your local environment")


# Load local environment variables
load_local_env()

# Set fallback defaults for local development
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/betterbundle"
)
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("GORSE_API_URL", "http://localhost:8088")
os.environ.setdefault("LOKI_URL", "http://localhost:3100")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "debug")
os.environ.setdefault("PORT", "8001")

# Import after setting environment variables
from app.core.config import settings
from app.core.logging.logger import setup_logging
from app.core.logging.config import LoggingConfig


def main():
    """Main function to run the local development server"""

    print("🚀 Starting BetterBundle Python Worker (Local Development)")
    print("=" * 60)
    print(f"Database URL: {os.environ.get('DATABASE_URL')}")
    print(f"Redis Host: {os.environ.get('REDIS_HOST')}:{os.environ.get('REDIS_PORT')}")
    print(f"Kafka Bootstrap Servers: {os.environ.get('KAFKA_BOOTSTRAP_SERVERS')}")
    print(f"Gorse API URL: {os.environ.get('GORSE_API_URL')}")
    print("=" * 60)

    # Setup logging configuration
    logging_config = LoggingConfig(
        level=settings.logging.LOG_LEVEL,
        format=settings.logging.LOG_FORMAT,
        file=settings.logging.LOGGING["file"],
        console=settings.logging.LOGGING["console"],
        prometheus=settings.logging.LOGGING["prometheus"],
        grafana=settings.logging.LOGGING["grafana"],
        telemetry=settings.logging.LOGGING["telemetry"],
        gcp=settings.logging.LOGGING["gcp"],
        aws=settings.logging.LOGGING["aws"],
    )

    # Setup logging before starting uvicorn
    setup_logging(logging_config)

    # Configure uvicorn for local development
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        reload=True,  # Enable auto-reload for development
        log_level="debug",
        log_config=None,  # Use our custom logging config
        access_log=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Shutting down BetterBundle Python Worker...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)
