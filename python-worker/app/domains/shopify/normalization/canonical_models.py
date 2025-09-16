from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


CANONICAL_VERSION = 1


class CanonicalLineItem(BaseModel):
    productId: Optional[str] = None
    variantId: Optional[str] = None
    title: Optional[str] = None
    quantity: int = 0
    price: float = 0.0


class CanonicalOrder(BaseModel):
    """Canonical order model - matches OrderData table structure exactly"""

    canonicalVersion: int = Field(default=CANONICAL_VERSION)
    shopId: str
    entityId: str  # Maps to orderId

    # Exact field mapping to OrderData table
    orderName: Optional[str] = None  # orderName
    customerId: Optional[str] = None  # customerId
    customerEmail: Optional[str] = None  # customerEmail (was email)
    customerPhone: Optional[str] = None  # customerPhone (was phone)
    customerDisplayName: Optional[str] = None  # customerDisplayName
    customerState: Optional[str] = None  # customerState
    customerVerifiedEmail: Optional[bool] = False  # customerVerifiedEmail
    customerCreatedAt: Optional[datetime] = None  # customerCreatedAt
    customerUpdatedAt: Optional[datetime] = None  # customerUpdatedAt
    customerDefaultAddress: Optional[Dict[str, Any]] = None  # customerDefaultAddress
    totalAmount: float = 0.0  # totalAmount
    subtotalAmount: Optional[float] = 0.0  # subtotalAmount
    totalTaxAmount: Optional[float] = 0.0  # totalTaxAmount
    totalShippingAmount: Optional[float] = 0.0  # totalShippingAmount
    totalRefundedAmount: Optional[float] = 0.0  # totalRefundedAmount
    totalOutstandingAmount: Optional[float] = 0.0  # totalOutstandingAmount
    orderDate: datetime  # orderDate (shopifyCreatedAt)
    processedAt: Optional[datetime] = None  # processedAt
    cancelledAt: Optional[datetime] = None  # cancelledAt
    cancelReason: Optional[str] = ""  # cancelReason
    orderLocale: Optional[str] = "en"  # orderLocale
    currencyCode: Optional[str] = "USD"  # currencyCode
    presentmentCurrencyCode: Optional[str] = "USD"  # presentmentCurrencyCode
    confirmed: bool = False  # confirmed
    test: bool = False  # test
    financialStatus: Optional[str] = None  # financialStatus
    fulfillmentStatus: Optional[str] = None  # fulfillmentStatus
    orderStatus: Optional[str] = None  # orderStatus
    tags: List[str] = Field(default_factory=list)  # tags (JSON)
    note: Optional[str] = ""  # note
    noteAttributes: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # noteAttributes (JSON)
    lineItems: List[CanonicalLineItem] = Field(default_factory=list)  # lineItems (JSON)
    shippingAddress: Optional[Dict[str, Any]] = None  # shippingAddress (JSON)
    billingAddress: Optional[Dict[str, Any]] = None  # billingAddress (JSON)
    discountApplications: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # discountApplications (JSON)
    metafields: List[Dict[str, Any]] = Field(default_factory=list)  # metafields (JSON)
    fulfillments: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # fulfillments (JSON)
    transactions: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # transactions (JSON)

    # Internal fields
    shopifyCreatedAt: datetime  # Used for orderDate
    shopifyUpdatedAt: datetime

    # Preserve unknown fields from raw payloads
    extras: Dict[str, Any] = Field(default_factory=dict)


class CanonicalVariant(BaseModel):
    variantId: Optional[str] = None
    title: Optional[str] = None
    price: Optional[float] = None
    compareAtPrice: Optional[float] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    inventory: Optional[int] = None


class CanonicalProduct(BaseModel):
    """Canonical product model - matches ProductData table structure exactly"""

    canonicalVersion: int = Field(default=CANONICAL_VERSION)
    shopId: str
    entityId: str  # Maps to productId

    # Exact field mapping to ProductData table
    title: str  # title (required)
    handle: str  # handle (required)
    description: Optional[str] = None  # description
    descriptionHtml: Optional[str] = None  # descriptionHtml
    productType: Optional[str] = ""  # productType
    vendor: Optional[str] = ""  # vendor
    tags: List[str] = Field(default_factory=list)  # tags (JSON)
    status: Optional[str] = "ACTIVE"  # status
    totalInventory: Optional[int] = 0  # totalInventory
    price: float = 0.0  # price
    compareAtPrice: Optional[float] = 0.0  # compareAtPrice
    inventory: Optional[int] = 0  # inventory
    imageUrl: Optional[str] = None  # imageUrl
    imageAlt: Optional[str] = None  # imageAlt
    productCreatedAt: Optional[datetime] = None  # productCreatedAt
    productUpdatedAt: Optional[datetime] = None  # productUpdatedAt
    onlineStoreUrl: Optional[str] = None  # onlineStoreUrl
    onlineStorePreviewUrl: Optional[str] = None  # onlineStorePreviewUrl
    seoTitle: Optional[str] = None  # seoTitle
    seoDescription: Optional[str] = None  # seoDescription
    templateSuffix: Optional[str] = None  # templateSuffix
    variants: List[CanonicalVariant] = Field(default_factory=list)  # variants (JSON)
    images: List[Dict[str, Any]] = Field(default_factory=list)  # images (JSON)
    options: List[Dict[str, Any]] = Field(default_factory=list)  # options (JSON)
    metafields: List[Dict[str, Any]] = Field(default_factory=list)  # metafields (JSON)

    # Internal fields
    shopifyCreatedAt: datetime  # Used for productCreatedAt
    shopifyUpdatedAt: datetime  # Used for productUpdatedAt
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Dict[str, Any] = Field(default_factory=dict)


class CanonicalCollection(BaseModel):
    """Canonical collection model - matches CollectionData table structure exactly"""

    canonicalVersion: int = Field(default=CANONICAL_VERSION)
    shopId: str
    entityId: str  # Maps to collectionId

    # Exact field mapping to CollectionData table
    title: str  # title (required)
    handle: str  # handle (required)
    description: Optional[str] = ""  # description
    templateSuffix: Optional[str] = ""  # templateSuffix
    seoTitle: Optional[str] = ""  # seoTitle
    seoDescription: Optional[str] = ""  # seoDescription
    imageUrl: Optional[str] = None  # imageUrl
    imageAlt: Optional[str] = None  # imageAlt
    productCount: int = 0  # productCount
    isAutomated: bool = False  # isAutomated
    metafields: List[Dict[str, Any]] = Field(default_factory=list)  # metafields (JSON)

    # Internal fields
    shopifyCreatedAt: datetime
    shopifyUpdatedAt: datetime
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Dict[str, Any] = Field(default_factory=dict)


class CanonicalCustomer(BaseModel):
    """Canonical customer model - matches CustomerData table structure exactly"""

    canonicalVersion: int = Field(default=CANONICAL_VERSION)
    shopId: str
    entityId: str  # Maps to customerId

    # Exact field mapping to CustomerData table
    email: Optional[str] = None  # email
    firstName: Optional[str] = None  # firstName
    lastName: Optional[str] = None  # lastName
    totalSpent: float = 0.0  # totalSpent
    orderCount: int = 0  # orderCount
    lastOrderDate: Optional[datetime] = None  # lastOrderDate
    tags: List[str] = Field(default_factory=list)  # tags (JSON)
    createdAtShopify: Optional[datetime] = None  # createdAtShopify
    lastOrderId: Optional[str] = None  # lastOrderId
    location: Optional[Dict[str, Any]] = None  # location (JSON)
    metafields: List[Dict[str, Any]] = Field(default_factory=list)  # metafields (JSON)
    state: Optional[str] = ""  # state
    verifiedEmail: bool = False  # verifiedEmail
    taxExempt: bool = False  # taxExempt
    defaultAddress: Optional[Dict[str, Any]] = None  # defaultAddress (JSON)
    addresses: List[Dict[str, Any]] = Field(default_factory=list)  # addresses (JSON)
    currencyCode: Optional[str] = "USD"  # currencyCode
    customerLocale: Optional[str] = "en"  # customerLocale

    # Internal fields
    shopifyCreatedAt: datetime  # Used for createdAtShopify
    shopifyUpdatedAt: datetime
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Dict[str, Any] = Field(default_factory=dict)


class NormalizeJob(BaseModel):
    event_type: str
    data_type: str  # orders|products|customers|collections
    format: str  # rest|graphql
    shop_id: str
    raw_id: Optional[str] = None
    shopify_id: Optional[str] = None
    timestamp: datetime
