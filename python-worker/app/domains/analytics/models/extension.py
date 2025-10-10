"""
Extension Models for Unified Analytics

Defines the different extension types and their contexts for proper
analytics tracking and attribution.
"""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ExtensionType(str, Enum):
    """Extension types in the BetterBundle ecosystem"""

    VENUS = "venus"  # Customer account extensions
    ATLAS = "atlas"  # Web pixels (behavioral tracking)
    PHOENIX = "phoenix"  # Checkout UI extensions
    APOLLO = "apollo"  # Post-purchase extensions
    MERCURY = "mercury"  # Shopify Plus checkout extensions


class ExtensionContext(str, Enum):
    """Context where extensions can run"""

    # Venus contexts
    CUSTOMER_PROFILE = "customer_profile"
    ORDER_STATUS = "order_status"
    ORDER_INDEX = "order_index"

    # Atlas contexts (everywhere except checkout)
    HOMEPAGE = "homepage"
    PRODUCT_PAGE = "product_page"
    COLLECTION_PAGE = "collection_page"
    CART_PAGE = "cart_page"
    SEARCH_PAGE = "search_page"
    CUSTOMER_ACCOUNT = "customer_account"

    # Phoenix contexts (currently cart, future expansion)
    CART_DRAWER = "cart_drawer"
    # Future: HOMEPAGE, PRODUCT_PAGE, COLLECTION_PAGE

    # Apollo contexts
    POST_PURCHASE = "post_purchase"
    THANK_YOU_PAGE = "thank_you_page"

    # Mercury contexts (Shopify Plus checkout)
    CHECKOUT_PAGE = "checkout_page"


class ExtensionCapability(BaseModel):
    """Extension capability definition"""

    extension_type: ExtensionType
    supported_contexts: list[ExtensionContext]
    can_track_behavior: bool = False
    can_show_recommendations: bool = False
    can_track_attribution: bool = False
    can_access_customer_data: bool = False


# Extension capability definitions
EXTENSION_CAPABILITIES: Dict[ExtensionType, ExtensionCapability] = {
    ExtensionType.VENUS: ExtensionCapability(
        extension_type=ExtensionType.VENUS,
        supported_contexts=[
            ExtensionContext.CUSTOMER_PROFILE,
            ExtensionContext.ORDER_STATUS,
            ExtensionContext.ORDER_INDEX,
        ],
        can_track_behavior=True,
        can_show_recommendations=True,
        can_track_attribution=True,
        can_access_customer_data=True,
    ),
    ExtensionType.ATLAS: ExtensionCapability(
        extension_type=ExtensionType.ATLAS,
        supported_contexts=[
            ExtensionContext.HOMEPAGE,
            ExtensionContext.PRODUCT_PAGE,
            ExtensionContext.COLLECTION_PAGE,
            ExtensionContext.CART_PAGE,
            ExtensionContext.SEARCH_PAGE,
            ExtensionContext.CUSTOMER_ACCOUNT,
        ],
        can_track_behavior=True,
        can_show_recommendations=False,
        can_track_attribution=False,
        can_access_customer_data=False,
    ),
    ExtensionType.PHOENIX: ExtensionCapability(
        extension_type=ExtensionType.PHOENIX,
        supported_contexts=[
            ExtensionContext.CART_PAGE,
            ExtensionContext.CART_DRAWER,
            # Future: HOMEPAGE, PRODUCT_PAGE, COLLECTION_PAGE
        ],
        can_track_behavior=True,
        can_show_recommendations=True,
        can_track_attribution=True,
        can_access_customer_data=False,
    ),
    ExtensionType.APOLLO: ExtensionCapability(
        extension_type=ExtensionType.APOLLO,
        supported_contexts=[
            ExtensionContext.POST_PURCHASE,
            ExtensionContext.THANK_YOU_PAGE,
        ],
        can_track_behavior=True,
        can_show_recommendations=True,
        can_track_attribution=True,
        can_access_customer_data=False,
    ),
    ExtensionType.MERCURY: ExtensionCapability(
        extension_type=ExtensionType.MERCURY,
        supported_contexts=[
            ExtensionContext.CHECKOUT_PAGE,
        ],
        can_track_behavior=True,
        can_show_recommendations=True,
        can_track_attribution=True,
        can_access_customer_data=True,  # Mercury has access to customer data in checkout
    ),
}


def get_extension_capability(extension_type: ExtensionType) -> ExtensionCapability:
    """Get capability definition for an extension type"""
    return EXTENSION_CAPABILITIES[extension_type]


def can_extension_run_in_context(
    extension_type: ExtensionType, context: ExtensionContext
) -> bool:
    """Check if an extension can run in a specific context"""
    capability = get_extension_capability(extension_type)
    return context in capability.supported_contexts


def get_extensions_for_context(context: ExtensionContext) -> list[ExtensionType]:
    """Get all extensions that can run in a specific context"""
    return [
        ext_type
        for ext_type, capability in EXTENSION_CAPABILITIES.items()
        if context in capability.supported_contexts
    ]
