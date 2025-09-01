"""
Response models for the ML API
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class BaseResponse(BaseModel):
    """Base response model"""

    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class ErrorResponse(BaseResponse):
    """Error response model"""

    success: bool = False
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class BundleAnalysisResponse(BaseResponse):
    """Response model for bundle analysis"""

    success: bool = True
    bundles: List[Dict[str, Any]] = Field(..., description="Generated bundles")
    similarity_matrix: Optional[List[List[float]]] = Field(
        None, description="Similarity matrix (for debugging)"
    )
    metadata: Dict[str, Any] = Field(..., description="Analysis metadata")


class SimpleBundleAnalysisResponse(BaseResponse):
    """Simple response model for bundle analysis - only success/fail"""

    success: bool = True
    message: str = Field(..., description="Analysis result message")
    bundles_generated: Optional[int] = Field(
        None, description="Number of bundles generated"
    )


class CosineSimilarityResponse(BaseResponse):
    """Response model for cosine similarity calculation"""

    success: bool = True
    similarities: List[Dict[str, Any]] = Field(..., description="Similarity results")
    matrix: Optional[List[List[float]]] = Field(None, description="Similarity matrix")
    metadata: Dict[str, Any] = Field(..., description="Analysis metadata")


class BundleRetrievalResponse(BaseResponse):
    """Response model for bundle retrieval"""

    success: bool = True
    bundles: List[Dict[str, Any]] = Field(..., description="Retrieved bundles")
    total: int = Field(..., description="Total number of bundles")
    message: str = Field(..., description="Retrieval result message")


class HealthCheckResponse(BaseResponse):
    """Response model for health check"""

    success: bool = True
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    database: bool = Field(..., description="Database connection status")


class ConfigurationResponse(BaseResponse):
    """Response model for configuration operations"""

    success: bool = True
    config: Dict[str, Any] = Field(..., description="Current configuration")
    message: str = Field(..., description="Configuration operation result")
