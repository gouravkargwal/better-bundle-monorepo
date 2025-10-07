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
    BillingPlanType,
    BillingPlanStatus,
    BillingCycle,
    InvoiceStatus,
    ExtensionType,
    AppBlockTarget,
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
    CustomerBehaviorFeatures,
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


# Billing models
from .billing import (
    BillingPlan,
    BillingInvoice,
)

# Commission models
from .commission import CommissionRecord

# Trial configuration models
from .trial_config import TrialConfig

# Extension models

# Export all models
__all__ = [
    # Base
    "Base",
    # Enums
    "RawSourceType",
    "RawDataFormat",
    "BillingPlanType",
    "BillingPlanStatus",
    "BillingCycle",
    "InvoiceStatus",
    "ExtensionType",
    "AppBlockTarget",
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
    "CustomerBehaviorFeatures",
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
    # Billing models
    "BillingPlan",
    "BillingInvoice",
    "CommissionRecord",
    # Trial configuration models
    "TrialConfig",
    # Extension models
]
