from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CanonicalLineItem(BaseModel):
    productId: Optional[str] = None
    variantId: Optional[str] = None
    title: Optional[str] = None
    quantity: int = 0
    price: float = 0.0
    properties: Any = Field(default_factory=dict)


class CanonicalOrder(BaseModel):
    """Canonical order model - matches OrderData table structure exactly"""

    shopId: str
    orderId: str  # Maps to orderId
    originalGid: Optional[str] = None  # Shopify GraphQL ID

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
    tags: Any = Field(default_factory=list)  # tags (JSON)
    note: Optional[str] = ""  # note
    noteAttributes: Any = Field(default_factory=list)  # noteAttributes (JSON)
    lineItems: List[CanonicalLineItem] = Field(
        default_factory=list
    )  # Extracted separately for LineItemData records
    shippingAddress: Any = Field(default_factory=dict)  # shippingAddress (JSON)
    billingAddress: Any = Field(default_factory=dict)  # billingAddress (JSON)
    discountApplications: Any = Field(
        default_factory=list
    )  # discountApplications (JSON)
    metafields: Any = Field(default_factory=list)  # metafields (JSON)
    fulfillments: Any = Field(default_factory=list)  # fulfillments (JSON)
    transactions: Any = Field(default_factory=list)  # transactions (JSON)
    refunds: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # refunds from GraphQL orders

    # Internal fields
    createdAt: datetime  # Used for orderDate
    updatedAt: datetime

    # Preserve unknown fields from raw payloads
    extras: Any = Field(default_factory=dict)


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

    shopId: str
    productId: str  # Maps to productId
    originalGid: Optional[str] = None  # Shopify GraphQL ID

    # Exact field mapping to ProductData table
    title: str  # title (required)
    handle: str  # handle (required)
    description: Optional[str] = None  # description
    descriptionHtml: Optional[str] = None  # descriptionHtml
    productType: Optional[str] = ""  # productType
    vendor: Optional[str] = ""  # vendor
    tags: Any = Field(default_factory=list)  # tags (JSON)
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
    variants: Any = Field(default_factory=list)  # variants (JSON)
    images: Any = Field(default_factory=list)  # images (JSON)
    media: Any = Field(default_factory=list)  # media (JSON)
    options: Any = Field(default_factory=list)  # options (JSON)
    metafields: Any = Field(default_factory=list)  # metafields (JSON)

    # Internal fields
    createdAt: datetime  # Used for productCreatedAt
    updatedAt: datetime  # Used for productUpdatedAt
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Any = Field(default_factory=dict)


class CanonicalCollection(BaseModel):
    """Canonical collection model - matches CollectionData table structure exactly"""

    shopId: str
    collectionId: str  # Maps to collectionId
    originalGid: Optional[str] = None  # Shopify GraphQL ID
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
    metafields: Any = Field(default_factory=list)  # metafields (JSON)

    # Internal fields
    createdAt: datetime
    updatedAt: datetime
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Any = Field(default_factory=dict)


class CanonicalCustomer(BaseModel):
    """Canonical customer model - matches CustomerData table structure exactly"""

    shopId: str
    customerId: str  # Maps to customerId
    originalGid: Optional[str] = None  # Shopify GraphQL ID

    # Exact field mapping to CustomerData table
    email: Optional[str] = None  # email
    firstName: Optional[str] = None  # firstName
    lastName: Optional[str] = None  # lastName
    totalSpent: float = 0.0  # totalSpent
    orderCount: int = 0  # orderCount
    lastOrderDate: Optional[datetime] = None  # lastOrderDate
    tags: Any = Field(default_factory=list)  # tags (JSON)
    customerCreatedAt: Optional[datetime] = None  # Rename this
    customerUpdatedAt: Optional[datetime] = None  # Rename this
    lastOrderId: Optional[str] = None  # lastOrderId
    location: Any = Field(default_factory=dict)  # location (JSON)
    metafields: Any = Field(default_factory=list)  # metafields (JSON)
    state: Optional[str] = ""  # state
    verifiedEmail: bool = False  # verifiedEmail
    taxExempt: bool = False  # taxExempt
    defaultAddress: Any = Field(default_factory=dict)  # defaultAddress (JSON)
    addresses: Any = Field(default_factory=list)  # addresses (JSON)
    currencyCode: Optional[str] = "USD"  # currencyCode
    customerLocale: Optional[str] = "en"  # customerLocale

    # Internal fields
    createdAt: datetime  # Used for createdAt
    updatedAt: datetime  # Used for updatedAt
    isActive: bool = True  # For soft deletes

    # Preserve unknown fields from raw payloads
    extras: Any = Field(default_factory=dict)


class CanonicalRefundLineItem(BaseModel):
    """Canonical refund line item model"""

    refundId: str
    orderId: str
    productId: Optional[str] = None
    variantId: Optional[str] = None
    quantity: int
    unitPrice: float
    refundAmount: float
    properties: Any = Field(default_factory=dict)


class CanonicalRefund(BaseModel):
    """Canonical refund model - matches RefundData table structure exactly"""

    shopId: str
    orderId: str  # Maps to orderId (BigInt)
    refundId: str  # Maps to refundId
    originalGid: Optional[str] = None  # Shopify GraphQL ID

    # Exact field mapping to RefundData table
    refundedAt: datetime  # refundedAt
    note: Optional[str] = ""  # note
    restock: bool = False  # restock
    totalRefundAmount: float  # totalRefundAmount
    currencyCode: str = "USD"  # currencyCode

    # Line items for RefundLineItemData records
    refundLineItems: List[CanonicalRefundLineItem] = Field(default_factory=list)

    # Internal fields
    createdAt: datetime
    updatedAt: datetime

    # Preserve unknown fields from raw payloads
    extras: Any = Field(default_factory=dict)


class NormalizeJob(BaseModel):
    event_type: str
    data_type: str  # orders|products|customers|collections
    format: str  # rest|graphql
    shop_id: str
    raw_id: Optional[str] = None
    shopify_id: Optional[Union[str, int]] = None  # Accept both string and integer
    timestamp: datetime
