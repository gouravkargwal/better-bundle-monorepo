"""
Enum models for SQLAlchemy

Defines all database enums used in the application.
"""

from enum import Enum


class RawSourceType(str, Enum):
    """Source type for raw data"""

    WEBHOOK = "webhook"
    BACKFILL = "backfill"


class RawDataFormat(str, Enum):
    """Data format for raw data"""

    REST = "rest"
    GRAPHQL = "graphql"


class InvoiceStatus(str, Enum):
    """Invoice status"""

    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


class ExtensionType(str, Enum):
    """Extension types"""

    APOLLO = "apollo"
    ATLAS = "atlas"
    VENUS = "venus"
    MERCURY = "mercury"  # Shopify Plus checkout extensions


class AppBlockTarget(str, Enum):
    """App block targets for Venus extensions"""

    CUSTOMER_ACCOUNT_ORDER_STATUS_BLOCK_RENDER = (
        "customer_account_order_status_block_render"
    )
    CUSTOMER_ACCOUNT_ORDER_INDEX_BLOCK_RENDER = (
        "customer_account_order_index_block_render"
    )
    CUSTOMER_ACCOUNT_PROFILE_BLOCK_RENDER = "customer_account_profile_block_render"
    CHECKOUT_POST_PURCHASE = "checkout_post_purchase"
    THEME_APP_EXTENSION = "theme_app_extension"
    WEB_PIXEL_EXTENSION = "web_pixel_extension"


# ============= NEW ENUMS FOR REDESIGNED BILLING SYSTEM =============


class SubscriptionPlanType(str, Enum):
    """Subscription plan types"""

    USAGE_BASED = "usage_based"
    TIERED = "tiered"
    FLAT_RATE = "flat_rate"
    HYBRID = "hybrid"


class SubscriptionStatus(str, Enum):
    """Status of subscription — single axis, no subscription_type needed.

    Flow: TRIAL → ACTIVE → SUSPENDED / CANCELLED / EXPIRED

    PENDING_APPROVAL has been removed — the merchant stays in TRIAL until the
    APP_SUBSCRIPTIONS_UPDATE webhook confirms ACTIVE. The UI checks the
    confirmation_url field to determine if billing setup has been initiated.
    """

    TRIAL = (
        "TRIAL"  # Trial in progress (may have confirmation_url for pending approval)
    )
    ACTIVE = "ACTIVE"  # Paid subscription active
    SUSPENDED = "SUSPENDED"  # Cap reached or payment issue
    CANCELLED = "CANCELLED"  # Cancelled by user/system
    EXPIRED = "EXPIRED"  # Naturally expired


class BillingCycleStatus(str, Enum):
    """Billing cycle status"""

    ACTIVE = "active"  # Current billing cycle
    COMPLETED = "completed"  # Cycle ended normally
    CANCELLED = "cancelled"  # Cycle cancelled (subscription ended)
    SUSPENDED = "suspended"  # Cycle suspended


class ShopifySubscriptionStatus(str, Enum):
    """Shopify subscription status"""

    PENDING = "pending"  # Awaiting merchant approval
    ACTIVE = "active"  # Active and billing
    DECLINED = "declined"  # Merchant declined
    CANCELLED = "cancelled"  # Cancelled
    EXPIRED = "expired"  # Expired


class AdjustmentReason(str, Enum):
    """Billing cycle adjustment reasons"""

    CAP_INCREASE = "cap_increase"  # User requested cap increase
    PLAN_UPGRADE = "plan_upgrade"  # Upgraded to higher tier
    ADMIN_ADJUSTMENT = "admin_adjustment"  # Admin adjustment
    PROMOTION = "promotion"  # Promotional adjustment
    DISPUTE_RESOLUTION = "dispute_resolution"  # Dispute resolution
