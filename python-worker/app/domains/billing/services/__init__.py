"""
Billing Services Package

Pay-as-you-go pricing: the shop is charged a share of the revenue attributed to
recommendations, capped per 30-day cycle.

- BillingServiceV2: attribution intake + trial management
- CommissionServiceV2: turns an attribution into a commission, applying the cap
- ShopifyUsageBillingServiceV2: posts the commission to Shopify as a usage record
"""

from .billing_service_v2 import BillingServiceV2
from .commission_service_v2 import CommissionServiceV2
from .shopify_usage_billing_service_v2 import ShopifyUsageBillingServiceV2
from . import attribution_reconciler

__all__ = [
    "BillingServiceV2",
    "CommissionServiceV2",
    "ShopifyUsageBillingServiceV2",
    "attribution_reconciler",
]
