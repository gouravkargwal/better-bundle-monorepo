"""
Pydantic models for cosine similarity analysis
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ProductData(BaseModel):
    """Product data model for similarity analysis"""
    product_id: str
    title: str
    category: Optional[str] = None
    price: float
    tags: Optional[List[str]] = []
    description: Optional[str] = ""
    image_url: Optional[str] = None


class OrderData(BaseModel):
    """Order data model for bundle analysis"""
    order_id: str
    customer_id: Optional[str] = None
    total_amount: float
    order_date: str
    line_items: List[Dict[str, Any]]


class BundleAnalysisRequest(BaseModel):
    """Request model for bundle analysis"""
    shop_id: str
    products: List[ProductData]
    orders: List[OrderData]
    analysis_config: Optional[Dict[str, Any]] = {}


class CosineSimilarityRequest(BaseModel):
    """Request model for cosine similarity calculation"""
    product_features: List[Dict[str, Any]]
    target_product_id: Optional[str] = None
    top_k: int = 10


class BundleAnalysisResponse(BaseModel):
    """Response model for bundle analysis"""
    success: bool
    bundles: List[Dict[str, Any]]
    similarity_matrix: Optional[List[List[float]]] = None
    metadata: Dict[str, Any]
    error: Optional[str] = None


class CosineSimilarityResponse(BaseModel):
    """Response model for cosine similarity calculation"""
    success: bool
    similarities: List[Dict[str, Any]]
    matrix: Optional[List[List[float]]] = None
    metadata: Dict[str, Any]
    error: Optional[str] = None


class SimilarityConfig(BaseModel):
    """Configuration model for similarity calculations"""
    text_weight: float = 0.7
    numerical_weight: float = 0.3
    max_features: int = 1000
    ngram_range: tuple = (1, 2)
    min_similarity_threshold: float = 0.1
    top_k_similar_products: int = 10


class BundleConfig(BaseModel):
    """Configuration model for bundle analysis"""
    min_support: float = 0.01
    min_confidence: float = 0.3
    min_lift: float = 1.2
    max_bundle_size: int = 2
    lift_weight: float = 0.6
    confidence_weight: float = 0.3
    similarity_weight: float = 0.1
