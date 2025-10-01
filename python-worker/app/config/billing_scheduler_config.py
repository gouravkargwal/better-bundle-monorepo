"""
Billing Scheduler Configuration

Configuration settings for the billing scheduler service.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from pydantic import BaseSettings, Field


class BillingSchedulerConfig(BaseSettings):
    """Configuration for the billing scheduler service"""

    # Service settings
    service_name: str = "billing-scheduler"
    version: str = "1.0.0"

    # Scheduling settings
    default_billing_cycle: str = "monthly"
    billing_day_of_month: int = 1  # Day of month to run billing
    billing_hour: int = 2  # Hour (UTC) to run billing
    billing_minute: int = 0  # Minute to run billing

    # Processing settings
    max_concurrent_shops: int = 10  # Maximum shops to process concurrently
    shop_batch_size: int = 50  # Number of shops to process in each batch
    retry_attempts: int = 3  # Number of retry attempts for failed shops
    retry_delay_seconds: int = 30  # Delay between retry attempts

    # Billing calculation settings
    minimum_billing_amount: float = 0.01  # Minimum amount to create an invoice
    currency_code: str = "USD"  # Default currency
    trial_threshold_days: int = 30  # Trial period in days

    # Notification settings
    enable_notifications: bool = True
    notification_webhook_url: str = Field(None, env="BILLING_NOTIFICATION_WEBHOOK_URL")
    slack_webhook_url: str = Field(None, env="SLACK_WEBHOOK_URL")
    email_notifications: bool = Field(False, env="ENABLE_EMAIL_NOTIFICATIONS")

    # GitHub Actions integration
    github_webhook_secret: str = Field(None, env="GITHUB_WEBHOOK_SECRET")
    github_api_token: str = Field(None, env="GITHUB_API_TOKEN")

    # API settings
    api_base_url: str = Field("http://localhost:8000", env="API_BASE_URL")
    api_timeout_seconds: int = 300  # API timeout in seconds

    # Database settings
    database_connection_pool_size: int = 10
    database_query_timeout_seconds: int = 30

    # Logging settings
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_structured_logging: bool = True

    # Monitoring settings
    enable_metrics: bool = True
    metrics_endpoint: str = Field("/metrics", env="METRICS_ENDPOINT")
    health_check_interval_seconds: int = 60

    # Billing tiers configuration
    billing_tiers: List[Dict[str, Any]] = [
        {
            "name": "Starter",
            "min_revenue": 0,
            "max_revenue": 5000,
            "rate": 0.03,
            "capped_amount": 50.0,
            "trial_threshold": 100.0,
        },
        {
            "name": "Growth",
            "min_revenue": 5000,
            "max_revenue": 25000,
            "rate": 0.025,
            "capped_amount": 200.0,
            "trial_threshold": 500.0,
        },
        {
            "name": "Enterprise",
            "min_revenue": 25000,
            "max_revenue": None,
            "rate": 0.02,
            "capped_amount": 1000.0,
            "trial_threshold": 2000.0,
        },
    ]

    # Fraud detection settings
    enable_fraud_detection: bool = True
    fraud_detection_threshold: float = 0.8  # Risk score threshold
    fraud_detection_review_required: bool = True

    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # Cache TTL in seconds
    enable_parallel_processing: bool = True
    max_workers: int = 4  # Maximum worker threads for parallel processing

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global configuration instance
config = BillingSchedulerConfig()


def get_billing_period_for_date(date: datetime) -> Dict[str, datetime]:
    """
    Get billing period for a given date.

    Args:
        date: Date to get billing period for

    Returns:
        Dictionary with start_date and end_date
    """
    # Get the first day of the month for the given date
    first_day = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get the last day of the previous month
    last_day_previous_month = first_day - timedelta(days=1)

    # Get the first day of the previous month
    first_day_previous_month = last_day_previous_month.replace(day=1)

    return {"start_date": first_day_previous_month, "end_date": last_day_previous_month}


def get_next_billing_date() -> datetime:
    """
    Get the next scheduled billing date.

    Returns:
        Next billing date
    """
    now = datetime.utcnow()

    # Get next billing date (1st of next month at configured hour)
    if now.day >= config.billing_day_of_month:
        # If we're past the billing day this month, schedule for next month
        if now.month == 12:
            next_billing = now.replace(
                year=now.year + 1, month=1, day=config.billing_day_of_month
            )
        else:
            next_billing = now.replace(
                month=now.month + 1, day=config.billing_day_of_month
            )
    else:
        # Schedule for this month
        next_billing = now.replace(day=config.billing_day_of_month)

    # Set the time
    next_billing = next_billing.replace(
        hour=config.billing_hour, minute=config.billing_minute, second=0, microsecond=0
    )

    return next_billing


def get_shop_batch_size() -> int:
    """Get the configured shop batch size"""
    return config.shop_batch_size


def get_max_concurrent_shops() -> int:
    """Get the configured maximum concurrent shops"""
    return config.max_concurrent_shops


def get_retry_config() -> Dict[str, int]:
    """Get retry configuration"""
    return {
        "attempts": config.retry_attempts,
        "delay_seconds": config.retry_delay_seconds,
    }


def get_billing_tiers() -> List[Dict[str, Any]]:
    """Get billing tiers configuration"""
    return config.billing_tiers


def is_fraud_detection_enabled() -> bool:
    """Check if fraud detection is enabled"""
    return config.enable_fraud_detection


def get_fraud_detection_threshold() -> float:
    """Get fraud detection threshold"""
    return config.fraud_detection_threshold


def get_notification_config() -> Dict[str, Any]:
    """Get notification configuration"""
    return {
        "enabled": config.enable_notifications,
        "webhook_url": config.notification_webhook_url,
        "slack_webhook_url": config.slack_webhook_url,
        "email_enabled": config.email_notifications,
    }
