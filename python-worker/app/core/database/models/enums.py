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


class BillingPlanType(str, Enum):
    """Billing plan types"""

    REVENUE_SHARE = "revenue_share"
    PERFORMANCE_TIER = "performance_tier"
    HYBRID = "hybrid"
    USAGE_BASED = "usage_based"


class BillingPlanStatus(str, Enum):
    """Billing plan status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class BillingCycle(str, Enum):
    """Billing cycle types"""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class InvoiceStatus(str, Enum):
    """Invoice status"""

    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ExtensionType(str, Enum):
    """Extension types"""

    APOLLO = "apollo"
    ATLAS = "atlas"
    PHOENIX = "phoenix"
    VENUS = "venus"


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


class BillingPhase(str, Enum):
    """Billing phase enum"""

    TRIAL = "trial"
    PAID = "paid"


class CommissionStatus(str, Enum):
    """Commission record status"""

    # Trial phase statuses
    TRIAL_PENDING = "trial_pending"  # Tracked during trial, not charged
    TRIAL_COMPLETED = "trial_completed"  # Trial ended, moved to paid phase

    # Paid phase statuses
    PENDING = "pending"  # Ready to be sent to Shopify
    RECORDED = "recorded"  # Successfully sent to Shopify
    INVOICED = "invoiced"  # Included in monthly invoice

    # Error/rejection statuses
    REJECTED = "rejected"  # Cap reached, couldn't charge
    FAILED = "failed"  # Failed to send to Shopify
    CAPPED = "capped"  # Partial charge due to cap


class ChargeType(str, Enum):
    """Type of charge"""

    FULL = "full"  # Full commission charged
    PARTIAL = "partial"  # Partial due to cap
    OVERFLOW_ONLY = "overflow_only"  # Only overflow tracked
    TRIAL = "trial"  # During trial period
    REJECTED = "rejected"  # Not charged


# ============= NEW ENUMS FOR REDESIGNED BILLING SYSTEM =============


class SubscriptionPlanType(str, Enum):
    """Subscription plan types"""

    USAGE_BASED = "usage_based"
    TIERED = "tiered"
    FLAT_RATE = "flat_rate"
    HYBRID = "hybrid"


class SubscriptionStatus(str, Enum):
    """Shop subscription status"""

    TRIAL = "trial"  # In trial period
    PENDING_APPROVAL = (
        "pending_approval"  # Trial ended, waiting for subscription approval
    )
    ACTIVE = "active"  # Active subscription
    SUSPENDED = "suspended"  # Suspended (payment issues, etc.)
    CANCELLED = "cancelled"  # Cancelled by user
    EXPIRED = "expired"  # Expired (end date reached)


class BillingCycleStatus(str, Enum):
    """Billing cycle status"""

    ACTIVE = "active"  # Current billing cycle
    COMPLETED = "completed"  # Cycle ended normally
    CANCELLED = "cancelled"  # Cycle cancelled (subscription ended)
    SUSPENDED = "suspended"  # Cycle suspended


class TrialStatus(str, Enum):
    """Trial status"""

    ACTIVE = "active"  # Trial in progress
    COMPLETED = "completed"  # Trial completed (threshold reached)
    EXPIRED = "expired"  # Trial expired (time limit reached)
    CANCELLED = "cancelled"  # Trial cancelled


class ShopifySubscriptionStatus(str, Enum):
    """Shopify subscription status"""

    PENDING = "PENDING"  # Awaiting merchant approval
    ACTIVE = "ACTIVE"  # Active and billing
    DECLINED = "DECLINED"  # Merchant declined
    CANCELLED = "CANCELLED"  # Cancelled
    EXPIRED = "EXPIRED"  # Expired


class AdjustmentReason(str, Enum):
    """Billing cycle adjustment reasons"""

    CAP_INCREASE = "cap_increase"  # User requested cap increase
    PLAN_UPGRADE = "plan_upgrade"  # Upgraded to higher tier
    ADMIN_ADJUSTMENT = "admin_adjustment"  # Admin adjustment
    PROMOTION = "promotion"  # Promotional adjustment
    DISPUTE_RESOLUTION = "dispute_resolution"  # Dispute resolution
