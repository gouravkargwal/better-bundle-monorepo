"""
Configuration file for Shopify Data Collection Service
Update these values according to your setup
"""

# Shopify Configuration
SHOP_DOMAIN = "your-shop.myshopify.com"  # Replace with your shop domain
ACCESS_TOKEN = "your-access-token"  # Replace with your access token
SHOP_ID = "your-shop-id"  # Replace with your shop ID

# Data Collection Options
INCLUDE_PRODUCTS = True
INCLUDE_ORDERS = True
INCLUDE_CUSTOMERS = True
INCLUDE_COLLECTIONS = True

# Collection Settings
BATCH_SIZE = 250
TIMEOUT_SECONDS = 300
RATE_LIMIT_DELAY = 0.1
MAX_DAYS_BACK = 90

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Database Configuration (if needed)
DATABASE_URL = "your-database-url"
REDIS_URL = "your-redis-url"
