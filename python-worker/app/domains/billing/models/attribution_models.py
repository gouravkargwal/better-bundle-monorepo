"""
Attribution Models for Billing System
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class AttributionType(str, Enum):
    """Types of attribution"""

    DIRECT_CLICK = "direct_click"
    CROSS_EXTENSION = "cross_extension"
    TIME_DECAY = "time_decay"
    FIRST_CLICK = "first_click"
    LAST_CLICK = "last_click"


class AttributionStatus(str, Enum):
    """Status of attribution calculation"""

    PENDING = "pending"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class InteractionType(str, Enum):
    """Types of user interactions"""

    VIEW = "view"
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    CHECKOUT_START = "checkout_start"
    PURCHASE = "purchase"


class ExtensionType(str, Enum):
    """Extension types"""

    VENUS = "venus"
    PHOENIX = "phoenix"
    APOLLO = "apollo"
    ATLAS = "atlas"


class UserInteraction(BaseModel):
    """User interaction data for attribution"""

    id: str
    session_id: str
    customer_id: Optional[str]
    shop_id: str
    extension_type: ExtensionType
    interaction_type: InteractionType
    product_id: Optional[str]
    collection_id: Optional[str]
    recommendation_id: Optional[str]
    recommendation_position: Optional[int]
    value: Optional[Decimal]
    quantity: Optional[int]
    metadata: Dict[str, Any]
    created_at: datetime


class PurchaseEvent(BaseModel):
    """Purchase event data"""

    order_id: int
    customer_id: Optional[str]
    shop_id: str
    session_id: Optional[str]
    total_amount: Decimal
    currency: str
    products: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime] = None  # For post-purchase additions
    metadata: Dict[str, Any]


class AttributionBreakdown(BaseModel):
    """Individual attribution breakdown"""

    extension_type: ExtensionType
    product_id: Optional[str]
    attributed_amount: Decimal
    attribution_weight: float  # 0.0 to 1.0
    attribution_type: AttributionType
    interaction_id: Optional[str]
    metadata: Dict[str, Any]


class AttributionResult(BaseModel):
    """Result of attribution calculation"""

    order_id: int
    shop_id: str
    customer_id: Optional[str]
    session_id: Optional[str]

    # Attribution breakdown
    total_attributed_revenue: Decimal
    attribution_breakdown: List[AttributionBreakdown]

    # Metadata
    attribution_type: AttributionType
    status: AttributionStatus
    calculated_at: datetime
    metadata: Dict[str, Any]


class AttributionRule(BaseModel):
    """Attribution rule configuration"""

    name: str
    description: str
    rule_type: AttributionType
    enabled: bool = True

    # Rule parameters
    time_window_hours: int = 720  # 30 days default
    minimum_order_value: Decimal = Decimal("10.00")
    cross_extension_weight_primary: float = 0.7
    cross_extension_weight_secondary: float = 0.3

    # Fraud prevention
    max_interactions_per_session: int = 100
    max_attribution_per_interaction: Decimal = Decimal("1000.00")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class AttributionConfig(BaseModel):
    """Attribution configuration for a shop"""

    shop_id: str
    rules: List[AttributionRule]
    default_rule: AttributionType = AttributionType.DIRECT_CLICK
    fraud_detection_enabled: bool = True
    audit_trail_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class AttributionMetrics(BaseModel):
    """Attribution metrics for reporting"""

    shop_id: str
    period_start: datetime
    period_end: datetime

    # Interaction metrics
    total_interactions: int
    total_clicks: int
    total_views: int

    # Purchase metrics
    total_purchases: int
    total_revenue: Decimal
    attributed_revenue: Decimal
    attribution_rate: float  # attributed_revenue / total_revenue

    # Extension metrics
    extension_metrics: Dict[ExtensionType, Dict[str, Any]]

    # Performance metrics
    average_attribution_per_purchase: Decimal
    top_performing_extension: Optional[ExtensionType]
    conversion_rate: float  # purchases / interactions

    calculated_at: datetime


class FraudDetectionResult(BaseModel):
    """Result of fraud detection"""

    shop_id: str
    order_id: int
    is_fraud: bool
    fraud_reasons: List[str]
    detected_at: datetime
    metadata: Dict[str, Any]


class AttributionEvent(BaseModel):
    """Event for attribution processing"""

    event_type: str
    shop_id: str
    order_id: int
    customer_id: Optional[str]
    session_id: Optional[str]
    data: Dict[str, Any]
    occurred_at: datetime
    processed_at: Optional[datetime] = None
    status: str = "pending"
    metadata: Dict[str, Any] = Field(default_factory=dict)
