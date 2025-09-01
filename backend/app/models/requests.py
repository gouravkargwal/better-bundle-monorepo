"""
Request models for the ML API
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ProductData(BaseModel):
    """Product data model for similarity analysis"""

    product_id: str = Field(..., description="Unique product identifier")
    title: str = Field(..., description="Product title")
    category: Optional[str] = Field(None, description="Product category")
    price: float = Field(..., description="Product price", ge=0)
    tags: List[str] = Field(default_factory=list, description="Product tags")
    description: str = Field("", description="Product description")
    image_url: Optional[str] = Field(None, description="Product image URL")


class OrderData(BaseModel):
    """Order data model for bundle analysis"""

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    total_amount: float = Field(..., description="Order total amount", ge=0)
    order_date: str = Field(..., description="Order date in ISO format")
    line_items: List[Dict[str, Any]] = Field(..., description="Order line items")


class SimilarityConfig(BaseModel):
    """Configuration model for similarity calculations"""

    text_weight: float = Field(
        default=0.7, description="Weight for text-based similarity"
    )
    numerical_weight: float = Field(
        default=0.3, description="Weight for numerical similarity"
    )
    max_features: int = Field(default=1000, description="Maximum features for TF-IDF")
    ngram_range: tuple = Field(
        default=(1, 2), description="N-gram range for text processing"
    )
    min_similarity_threshold: float = Field(
        default=0.1, description="Minimum similarity threshold"
    )
    top_k_similar_products: int = Field(
        default=10, description="Number of top similar products"
    )


class BundleConfig(BaseModel):
    """Configuration model for bundle analysis"""

    min_support: float = Field(default=0.01, description="Minimum support threshold")
    min_confidence: float = Field(
        default=0.3, description="Minimum confidence threshold"
    )
    min_lift: float = Field(default=1.2, description="Minimum lift threshold")
    max_bundle_size: int = Field(default=2, description="Maximum bundle size")
    lift_weight: float = Field(default=0.6, description="Weight for lift in scoring")
    confidence_weight: float = Field(
        default=0.3, description="Weight for confidence in scoring"
    )
    similarity_weight: float = Field(
        default=0.1, description="Weight for similarity in scoring"
    )


class BundleAnalysisRequest(BaseModel):
    """Request model for bundle analysis"""

    shop_id: str = Field(..., description="Shop identifier")
    products: List[ProductData] = Field(..., description="List of products")
    orders: List[OrderData] = Field(..., description="List of orders")
    analysis_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Analysis configuration"
    )


class CosineSimilarityRequest(BaseModel):
    """Request model for cosine similarity calculation"""

    product_features: List[Dict[str, Any]] = Field(
        ..., description="List of product features"
    )
    target_product_id: Optional[str] = Field(
        None, description="Target product for similarity calculation"
    )
    top_k: int = Field(
        default=10, ge=1, le=100, description="Number of similar products to return"
    )


class ConfigurationUpdateRequest(BaseModel):
    """Request model for updating ML configuration"""

    similarity: Optional[Dict[str, Any]] = Field(
        None, description="Similarity configuration"
    )
    bundle: Optional[Dict[str, Any]] = Field(None, description="Bundle configuration")
