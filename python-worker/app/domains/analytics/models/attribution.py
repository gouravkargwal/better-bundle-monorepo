"""
Attribution Models for Unified Analytics

Handles purchase attribution across multiple extensions with proper
weighting and revenue tracking.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from decimal import Decimal

from .extension import ExtensionType


class AttributionWeight(BaseModel):
    """Attribution weight for a specific extension"""

    extension_type: ExtensionType = Field(..., description="Extension type")
    weight: float = Field(..., description="Attribution weight (0.0 to 1.0)")
    contribution_type: str = Field(
        ..., description="Type of contribution (discovery, conversion, etc.)"
    )

    @validator("weight")
    def validate_weight(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Attribution weight must be between 0.0 and 1.0")
        return v


class PurchaseAttribution(BaseModel):
    """Purchase attribution model for unified analytics"""

    id: str = Field(..., description="Unique attribution identifier")
    session_id: str = Field(..., description="Session identifier")
    order_id: str = Field(..., description="Order identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    # Attribution details
    contributing_extensions: List[ExtensionType] = Field(
        ..., description="Extensions that contributed to the purchase"
    )
    attribution_weights: List[AttributionWeight] = Field(
        ..., description="Attribution weights for each extension"
    )

    # Revenue tracking
    total_revenue: Decimal = Field(..., description="Total revenue from this purchase")
    attributed_revenue: Dict[ExtensionType, Decimal] = Field(
        ..., description="Revenue attributed to each extension"
    )

    # Interaction tracking
    total_interactions: int = Field(
        ..., description="Total interactions in the session"
    )
    interactions_by_extension: Dict[ExtensionType, int] = Field(
        ..., description="Interactions per extension"
    )

    # Timestamps
    purchase_at: datetime = Field(..., description="Purchase timestamp")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Attribution creation time"
    )

    # Metadata
    attribution_algorithm: str = Field(
        default="multi_touch", description="Algorithm used for attribution"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional attribution metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


class AttributionCreate(BaseModel):
    """Model for creating purchase attribution"""

    session_id: str = Field(..., description="Session identifier")
    order_id: str = Field(..., description="Order identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    # Revenue details
    total_revenue: Decimal = Field(..., description="Total revenue from this purchase")

    # Attribution algorithm
    attribution_algorithm: str = Field(
        default="multi_touch", description="Algorithm to use for attribution"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional attribution metadata"
    )

    @validator("total_revenue")
    def validate_total_revenue(cls, v):
        if v < 0:
            raise ValueError("Total revenue must be >= 0")
        return v


class AttributionQuery(BaseModel):
    """Model for querying purchase attributions"""

    session_id: Optional[str] = Field(None, description="Filter by session identifier")
    order_id: Optional[str] = Field(None, description="Filter by order identifier")
    customer_id: Optional[str] = Field(
        None, description="Filter by customer identifier"
    )
    shop_id: Optional[str] = Field(None, description="Filter by shop identifier")
    extension_type: Optional[ExtensionType] = Field(
        None, description="Filter by extension type"
    )
    purchase_after: Optional[datetime] = Field(
        None, description="Filter purchases after this time"
    )
    purchase_before: Optional[datetime] = Field(
        None, description="Filter purchases before this time"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AttributionSummary(BaseModel):
    """Summary of attribution data for reporting"""

    shop_id: str = Field(..., description="Shop identifier")
    period_start: datetime = Field(..., description="Period start time")
    period_end: datetime = Field(..., description="Period end time")

    # Overall metrics
    total_attributions: int = Field(..., description="Total number of attributions")
    total_revenue: Decimal = Field(..., description="Total attributed revenue")

    # Extension metrics
    revenue_by_extension: Dict[ExtensionType, Decimal] = Field(
        ..., description="Revenue attributed to each extension"
    )
    attributions_by_extension: Dict[ExtensionType, int] = Field(
        ..., description="Number of attributions per extension"
    )
    avg_attribution_weight: Dict[ExtensionType, float] = Field(
        ..., description="Average attribution weight per extension"
    )

    # Performance metrics
    conversion_rate: float = Field(..., description="Overall conversion rate")
    avg_revenue_per_attribution: Decimal = Field(
        ..., description="Average revenue per attribution"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}
