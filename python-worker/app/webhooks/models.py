# app/webhooks/models.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal, Union, Dict, Any

# --- Common Nested Models ---


class ProductVariant(BaseModel):
    id: str
    title: str
    sku: Optional[str] = None
    price: float
    product_id: str = Field(..., alias="productId")


class Cart(BaseModel):
    id: str
    lines: List[ProductVariant]
    total_quantity: int = Field(..., alias="totalQuantity")


class Checkout(BaseModel):
    id: str
    total_price: float = Field(..., alias="totalPrice")
    currency: str
    products: List[ProductVariant]


# --- Define Data Models for Each Specific Event ---


class PageViewedData(BaseModel):
    url: str
    referrer: Optional[str] = None


class ProductViewedData(BaseModel):
    product_variant: ProductVariant = Field(..., alias="productVariant")


class ProductAddedToCartData(BaseModel):
    cart: Cart
    product_variant: ProductVariant = Field(..., alias="productVariant")
    quantity: int


class CollectionViewedData(BaseModel):
    collection_id: str = Field(..., alias="collectionId")
    collection_title: str = Field(..., alias="collectionTitle")


class SearchSubmittedData(BaseModel):
    query: str
    results: List[ProductVariant]


class CheckoutStartedData(BaseModel):
    checkout: Checkout


class CheckoutCompletedData(BaseModel):
    checkout: Checkout


# A generic model for any events we don't have a specific structure for
class GenericEventData(BaseModel):
    class Config:
        extra = "allow"


# --- Create the Main Event Models with the Discriminated Union ---


class BaseEvent(BaseModel):
    id: str
    timestamp: datetime
    customer_id: Optional[str] = Field(None, alias="customerId")
    context: Optional[Dict[str, Any]] = None


class PageViewedEvent(BaseEvent):
    name: Literal["page_viewed"]
    data: PageViewedData


class ProductViewedEvent(BaseEvent):
    name: Literal["product_viewed"]
    data: ProductViewedData


class ProductAddedToCartEvent(BaseEvent):
    name: Literal["product_added_to_cart"]
    data: ProductAddedToCartData


class CollectionViewedEvent(BaseEvent):
    name: Literal["collection_viewed"]
    data: CollectionViewedData


class SearchSubmittedEvent(BaseEvent):
    name: Literal["search_submitted"]
    data: SearchSubmittedData


class CheckoutStartedEvent(BaseEvent):
    name: Literal["checkout_started"]
    data: CheckoutStartedData


class CheckoutCompletedEvent(BaseEvent):
    name: Literal["checkout_completed"]
    data: CheckoutCompletedData


# A fallback for any other standard event type we don't need detailed data for
class GenericEvent(BaseEvent):
    name: str
    data: Optional[GenericEventData] = None


# The main validator. Pydantic will check the 'name' field and pick the correct model.
ShopifyBehavioralEvent = Union[
    PageViewedEvent,
    ProductViewedEvent,
    ProductAddedToCartEvent,
    CollectionViewedEvent,
    SearchSubmittedEvent,
    CheckoutStartedEvent,
    CheckoutCompletedEvent,
    GenericEvent,  # Fallback must be last
]
