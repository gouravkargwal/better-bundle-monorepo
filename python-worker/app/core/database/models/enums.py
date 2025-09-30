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


class BillingEventType(str, Enum):
    """Billing event types"""

    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    METRICS_CALCULATED = "metrics_calculated"
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    REFUND_PROCESSED = "refund_processed"
    BILLING_SUSPENDED = "billing_suspended"
    BILLING_REACTIVATED = "billing_reactivated"


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
