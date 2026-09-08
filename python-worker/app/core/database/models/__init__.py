"""
SQLAlchemy models for BetterBundle Python Worker
"""

# Import all models for easy access
from .base import Base
from .enums import (
    SubscriptionPlanType,
    SubscriptionStatus,
    BillingCycleStatus,
    TrialStatus,
    ShopifySubscriptionStatus,
    AdjustmentReason,
    BillingPhase,
    CommissionStatus,
    ChargeType,
    SubscriptionType,
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

# Session and tracking
from .user_session import UserSession
from .purchase_attribution import PurchaseAttribution

# Product vectors (cross-encoder / bi-encoder embeddings)
from .identity import UserIdentityLink
from .product_vector import ProductVector
from .product_edge import ProductEdge, EDGE_TYPES, RECOMMENDABLE_EDGE_TYPES

# Offer tracking
from .offer_impression import OfferImpression

# New redesigned billing models
from .subscription_plan import SubscriptionPlan
from .shop_subscription import ShopSubscription
from .billing_cycle import BillingCycle

# Suspension audit log
from .suspension_audit_log import SuspensionAuditLog

# Export all models
__all__ = [
    "Base",
    "SubscriptionPlanType",
    "SubscriptionStatus",
    "BillingCycleStatus",
    "TrialStatus",
    "ShopifySubscriptionStatus",
    "AdjustmentReason",
    "BillingPhase",
    "CommissionStatus",
    "ChargeType",
    "SubscriptionType",
    "Shop",
    "Session",
    "OrderData",
    "LineItemData",
    "ProductData",
    "CustomerData",
    "CollectionData",
    "RawOrder",
    "RawProduct",
    "RawCustomer",
    "RawCollection",
    "UserSession",
    "PurchaseAttribution",
    "OfferImpression",
    "UserIdentityLink",
    "ProductVector",
    "ProductEdge",
    "EDGE_TYPES",
    "RECOMMENDABLE_EDGE_TYPES",
    "SubscriptionPlan",
    "ShopSubscription",
    "BillingCycle",
    "SuspensionAuditLog",
]
