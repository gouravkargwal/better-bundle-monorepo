from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal, Union, Dict, Any


class Money(BaseModel):
    amount: float
    currencyCode: str


class ImageRef(BaseModel):
    src: Optional[str] = None


class ProductRef(BaseModel):
    id: str
    title: Optional[str] = None
    untranslatedTitle: Optional[str] = None
    type: Optional[str] = None
    vendor: Optional[str] = None
    url: Optional[str] = None


class ProductVariant(BaseModel):
    id: str
    title: str
    untranslatedTitle: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Money] = None
    image: Optional[ImageRef] = None
    product: Optional[ProductRef] = None


class TotalAmount(BaseModel):
    totalAmount: Money


class CartLine(BaseModel):
    quantity: int
    merchandise: ProductVariant
    cost: Optional[TotalAmount] = None


class CheckoutLineItem(BaseModel):
    id: str
    title: Optional[str] = None
    quantity: int
    finalLinePrice: Optional[Money] = None
    discountAllocations: Optional[List[dict]] = None
    variant: Optional[ProductVariant] = None


class Transaction(BaseModel):
    amount: Money
    gateway: Optional[str] = None
    paymentMethod: Optional[dict] = None


class OrderRef(BaseModel):
    id: str
    isFirstOrder: Optional[bool] = None


class Checkout(BaseModel):
    id: str
    token: Optional[str] = None
    email: Optional[str] = None
    currencyCode: Optional[str] = None
    buyerAcceptsEmailMarketing: Optional[bool] = None
    buyerAcceptsSmsMarketing: Optional[bool] = None
    subtotalPrice: Optional[Money] = None
    totalPrice: Optional[Money] = None
    totalTax: Optional[Money] = None
    discountsAmount: Optional[Money] = None
    shippingLine: Optional[dict] = None
    billingAddress: Optional[dict] = None
    shippingAddress: Optional[dict] = None
    discountApplications: Optional[List[dict]] = None
    lineItems: List[CheckoutLineItem]
    transactions: Optional[List[Transaction]] = None
    order: Optional[OrderRef] = None


class PageViewedData(BaseModel):
    # Web Pixel sends minimal data for page_viewed; we keep this flexible
    url: Optional[str] = None
    referrer: Optional[str] = None

    class Config:
        extra = "allow"


class ProductViewedData(BaseModel):
    product_variant: ProductVariant = Field(..., alias="productVariant")


class ProductAddedToCartData(BaseModel):
    cartLine: CartLine


class CollectionObject(BaseModel):
    id: str
    title: Optional[str] = None
    productVariants: Optional[List[ProductVariant]] = None


class CollectionViewedData(BaseModel):
    collection: CollectionObject


class SearchResult(BaseModel):
    query: str
    productVariants: Optional[List[ProductVariant]] = None


class SearchSubmittedData(BaseModel):
    searchResult: SearchResult


class CheckoutStartedData(BaseModel):
    checkout: Checkout


class CheckoutCompletedData(BaseModel):
    checkout: Checkout


# A generic model for any events we don't have a specific structure for
class GenericEventData(BaseModel):
    class Config:
        extra = "allow"


class BaseEvent(BaseModel):
    id: str
    timestamp: datetime
    customer_id: Optional[str] = Field(None, alias="customerId")
    context: Optional[Dict[str, Any]] = None
    clientId: Optional[str] = None
    seq: Optional[int] = None
    type: Optional[str] = None


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
