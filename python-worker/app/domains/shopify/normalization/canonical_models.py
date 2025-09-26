from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CanonicalVariantData(BaseModel):
    """Canonical variant data model - stores complete variant information from paginated products"""

    variant_id: Optional[str] = None
    title: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    inventory_quantity: Optional[int] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    taxable: Optional[bool] = None
    inventory_policy: Optional[str] = None
    position: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    selected_options: Any = Field(default_factory=list)  # selectedOptions (JSON)


class CanonicalImageData(BaseModel):
    """Canonical image data model - stores complete image information from paginated products"""

    image_id: Optional[str] = None
    url: Optional[str] = None
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class CanonicalMetafieldData(BaseModel):
    """Canonical metafield data model - stores complete metafield information from paginated data"""

    metafield_id: Optional[str] = None
    namespace: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    type: Optional[str] = None


class CanonicalProductInCollection(BaseModel):
    """Canonical product in collection model - stores product data within collections"""

    product_id: Optional[str] = None
    title: Optional[str] = None
    handle: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Any = Field(default_factory=list)
    price_range: Any = Field(default_factory=dict)  # priceRangeV2 data


class CanonicalLineItem(BaseModel):
    """Canonical line item model - stores complete line item data from paginated orders"""

    productId: Optional[str] = None
    variantId: Optional[str] = None
    title: Optional[str] = None
    quantity: int = 0
    price: float = 0.0
    original_unit_price: Optional[float] = None  # From originalUnitPriceSet
    discounted_unit_price: Optional[float] = None  # From discountedUnitPriceSet
    currency_code: Optional[str] = None  # From price sets
    variant_data: Any = Field(default_factory=dict)  # Complete variant information
    properties: Any = Field(default_factory=dict)


class CanonicalOrder(BaseModel):
    """Canonical order model - matches OrderData table structure exactly"""

    shop_id: str
    order_id: str  # Maps to orderId
    order_name: Optional[str] = None  # orderName
    customer_id: Optional[str] = None  # customerId
    customer_email: Optional[str] = None  # customerEmail (was email)
    customer_phone: Optional[str] = None  # customerPhone (was phone)
    customer_display_name: Optional[str] = None  # customerDisplayName
    customer_state: Optional[str] = None  # customerState
    customer_verified_email: Optional[bool] = False  # customerVerifiedEmail
    customer_default_address: Optional[Dict[str, Any]] = None  # customerDefaultAddress
    total_amount: float = 0.0  # totalAmount
    subtotal_amount: Optional[float] = 0.0  # subtotalAmount
    total_tax_amount: Optional[float] = 0.0  # totalTaxAmount
    total_shipping_amount: Optional[float] = 0.0  # totalShippingAmount
    total_refunded_amount: Optional[float] = 0.0  # totalRefundedAmount
    total_outstanding_amount: Optional[float] = 0.0  # totalOutstandingAmount
    order_date: datetime  # orderDate (shopifyCreatedAt)
    processed_at: Optional[datetime] = None  # processedAt
    cancelled_at: Optional[datetime] = None  # cancelledAt
    cancel_reason: Optional[str] = ""  # cancelReason
    order_locale: Optional[str] = "en"  # orderLocale
    currency_code: Optional[str] = "USD"  # currencyCode
    presentment_currency_code: Optional[str] = "USD"  # presentmentCurrencyCode
    confirmed: bool = False  # confirmed
    test: bool = False  # test
    financial_status: Optional[str] = None  # financialStatus
    fulfillment_status: Optional[str] = None  # fulfillmentStatus
    order_status: Optional[str] = None  # orderStatus
    tags: Any = Field(default_factory=list)  # tags (JSON)
    note: Optional[str] = ""  # note
    note_attributes: Any = Field(default_factory=list)  # noteAttributes (JSON)
    lineItems: List[CanonicalLineItem] = Field(
        default_factory=list
    )  # Extracted separately for LineItemData records - complete paginated line items
    shipping_address: Any = Field(default_factory=dict)  # shippingAddress (JSON)
    billing_address: Any = Field(default_factory=dict)  # billingAddress (JSON)
    discount_applications: Any = Field(
        default_factory=list
    )  # discountApplications (JSON)
    metafields: Any = Field(default_factory=list)  # metafields (JSON)
    fulfillments: Any = Field(default_factory=list)  # fulfillments (JSON)
    transactions: Any = Field(default_factory=list)  # transactions (JSON)
    refunds: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # refunds from GraphQL orders

    # Internal fields
    created_at: datetime  # Used for orderDate
    updated_at: datetime
    extras: Any = Field(default_factory=dict)


class CanonicalVariant(BaseModel):
    variant_id: Optional[str] = None
    title: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    inventory: Optional[int] = None


class CanonicalProduct(BaseModel):
    """Canonical product model - matches ProductData table structure exactly"""

    shop_id: str
    product_id: str  # Maps to productId
    # Exact field mapping to ProductData table
    title: str  # title (required)
    handle: str  # handle (required)
    # Core product information (essential for ML)
    description: Optional[str] = None  # description
    product_type: Optional[str] = ""  # productType
    vendor: Optional[str] = ""  # vendor
    tags: Any = Field(default_factory=list)  # tags (JSON)
    status: Optional[str] = "ACTIVE"  # status
    total_inventory: Optional[int] = 0  # totalInventory

    # Pricing data (essential for ML)
    price: float = 0.0  # price
    compare_at_price: Optional[float] = 0.0  # compareAtPrice
    price_range: Any = Field(default_factory=dict)  # price_range (JSON)

    # Collections data (critical for ML features)
    collections: Any = Field(default_factory=list)  # collections (JSON)

    # Timestamps (used in recency features)
    created_at: Optional[datetime] = None  # createdAt
    updated_at: Optional[datetime] = None  # updatedAt

    # SEO data (valuable for content-based ML features)
    seo_title: Optional[str] = None  # seoTitle
    seo_description: Optional[str] = None  # seoDescription
    template_suffix: Optional[str] = None  # templateSuffix

    # Detailed product data (essential for ML) - now stores complete paginated data
    variants: Any = Field(
        default_factory=list
    )  # variants (JSON) - all variants from pagination
    images: Any = Field(
        default_factory=list
    )  # images (JSON) - all images from pagination
    media: Any = Field(default_factory=list)  # media (JSON) - all media from pagination
    options: Any = Field(default_factory=list)  # options (JSON)
    metafields: Any = Field(
        default_factory=list
    )  # metafields (JSON) - all metafields from pagination

    # Note: Derived metrics are computed in feature engineering, not stored

    # Internal fields
    is_active: bool = True  # For soft deletes
    extras: Any = Field(default_factory=dict)


class CanonicalCollection(BaseModel):
    """Canonical collection model - matches CollectionData table structure exactly"""

    shop_id: str
    collection_id: str  # Maps to collectionId
    title: str  # title (required)
    handle: str  # handle (required)
    description: Optional[str] = ""  # description
    template_suffix: Optional[str] = ""  # templateSuffix
    seo_title: Optional[str] = ""  # seoTitle
    seo_description: Optional[str] = ""  # seoDescription
    image_url: Optional[str] = None  # imageUrl -> image_url to match DB schema
    image_alt: Optional[str] = None  # imageAlt
    product_count: int = 0  # productCount
    is_automated: bool = False  # isAutomated
    metafields: Any = Field(default_factory=list)  # metafields (JSON)
    products: Any = Field(
        default_factory=list
    )  # products (JSON) - complete paginated product data

    # Internal fields
    created_at: datetime
    updated_at: datetime
    is_active: bool = True  # For soft deletes
    extras: Any = Field(default_factory=dict)


class CanonicalCustomer(BaseModel):
    """Canonical customer model - matches CustomerData table structure exactly"""

    shop_id: str
    customer_id: str  # Maps to customerId
    # Exact field mapping to CustomerData table
    first_name: Optional[str] = None  # firstName
    last_name: Optional[str] = None  # lastName
    total_spent: float = 0.0  # totalSpent
    order_count: int = 0  # orderCount
    last_order_date: Optional[datetime] = None  # lastOrderDate
    last_order_id: Optional[str] = None  # lastOrderId
    verified_email: bool = False  # verifiedEmail
    tax_exempt: bool = False  # taxExempt
    customer_locale: Optional[str] = "en"  # customerLocale
    tags: Any = Field(default_factory=list)  # tags (JSON)
    state: Optional[str] = ""  # state
    default_address: Any = Field(default_factory=dict)  # defaultAddress (JSON)

    # Internal fields
    created_at: datetime  # Used for createdAt
    updated_at: datetime  # Used for updatedAt
    is_active: bool = True  # For soft deletes
    extras: Any = Field(default_factory=dict)


class CanonicalRefundLineItem(BaseModel):
    """Canonical refund line item model"""

    refund_id: str
    order_id: str
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    quantity: int
    unit_price: float
    refund_amount: float
    properties: Any = Field(default_factory=dict)


class CanonicalRefund(BaseModel):
    """Canonical refund model - matches RefundData table structure exactly"""

    shop_id: str
    order_id: str  # Maps to orderId (BigInt)
    refund_id: str  # Maps to refundId

    # Exact field mapping to RefundData table
    refunded_at: datetime  # refundedAt
    note: Optional[str] = ""  # note
    restock: bool = False  # restock
    total_refund_amount: float  # totalRefundAmount
    currency_code: str = "USD"  # currencyCode

    # Line items for RefundLineItemData records
    refund_line_items: List[CanonicalRefundLineItem] = Field(default_factory=list)

    # Internal fields
    created_at: datetime
    updated_at: datetime

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
