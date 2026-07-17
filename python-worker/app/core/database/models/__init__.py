"""
SQLAlchemy models for BetterBundle Python Worker

This module contains all SQLAlchemy models based on the Prisma schema.
Models are organized by functionality and include proper relationships,
indexes, and constraints.
"""

# Import all models for easy access
from .base import Base
from .enums import (
    RawSourceType,
    RawDataFormat,
    InvoiceStatus,
    ExtensionType,
    AppBlockTarget,
    # Billing system enums
    SubscriptionPlanType,
    SubscriptionStatus,
    BillingCycleStatus,
    ShopifySubscriptionStatus,
    AdjustmentReason,
)

# Core business models
from .shop import Shop
from .session import Session
from .order_data import OrderData, LineItemData
from .product_data import ProductData
from .customer_data import CustomerData
from .collection_data import CollectionData

# Raw data models
from .raw_data import (
    RawOrder,
    RawProduct,
    RawCustomer,
    RawCollection,
)

# Feature models
from .features import (
    UserFeatures,
    ProductFeatures,
    CollectionFeatures,
    InteractionFeatures,
    SessionFeatures,
    ProductPairFeatures,
    SearchProductFeatures,
)

# Identity models
from .identity import UserIdentityLink

# Session and interaction models
from .user_session import UserSession
from .user_interaction import UserInteraction
from .purchase_attribution import PurchaseAttribution

# Billing models (legacy - removed)
# Old billing models have been replaced with new subscription system

# New redesigned billing models
from .subscription_plan import SubscriptionPlan
from .shop_subscription import ShopSubscription

# Scheduler job execution tracking
from .scheduler_job_execution import SchedulerJobExecution

# Trial configuration models

# Export all models
__all__ = [
    # Base
    "Base",
    # Enums
    "RawSourceType",
    "RawDataFormat",
    "InvoiceStatus",
    "ExtensionType",
    "AppBlockTarget",
    # New enums for redesigned billing system
    "SubscriptionPlanType",
    "SubscriptionStatus",
    "BillingCycleStatus",
    "ShopifySubscriptionStatus",
    "AdjustmentReason",
    # Core models
    "Shop",
    "Session",
    "OrderData",
    "LineItemData",
    "ProductData",
    "CustomerData",
    "CollectionData",
    # Raw data models
    "RawOrder",
    "RawProduct",
    "RawCustomer",
    "RawCollection",
    # Feature models
    "UserFeatures",
    "ProductFeatures",
    "CollectionFeatures",
    "InteractionFeatures",
    "SessionFeatures",
    "ProductPairFeatures",
    "SearchProductFeatures",
    # Identity
    "UserIdentityLink",
    # Session and interaction
    "UserSession",
    "UserInteraction",
    "PurchaseAttribution",
    # New redesigned billing models
    "SubscriptionPlan",
    "ShopSubscription",
    # Extension models
    "SchedulerJobExecution",
]
