"""
Cosine Similarity Module for BetterBundle ML API
Handles product similarity calculations using cosine similarity and TF-IDF
"""

from .analyzer import BundleAnalyzer
from .models import (
    ProductData,
    OrderData,
    BundleAnalysisRequest,
    CosineSimilarityRequest,
    BundleAnalysisResponse,
    CosineSimilarityResponse,
    SimilarityConfig,
    BundleConfig,
)

__all__ = [
    "BundleAnalyzer",
    "ProductData",
    "OrderData",
    "BundleAnalysisRequest",
    "CosineSimilarityRequest",
    "BundleAnalysisResponse",
    "CosineSimilarityResponse",
    "SimilarityConfig",
    "BundleConfig",
]
