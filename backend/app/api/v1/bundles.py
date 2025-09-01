"""
Bundle analysis API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma
from app.core.database import get_db
from app.services.bundle_analysis import BundleAnalysisService
from app.models.responses import SimpleBundleAnalysisResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/{shop_id}", response_model=SimpleBundleAnalysisResponse)
async def analyze_bundles_from_database(
    shop_id: str, db: Prisma = Depends(get_db)
) -> SimpleBundleAnalysisResponse:
    """
    Analyze bundles using data from database

    Args:
        shop_id: Shop identifier
        db: Database dependency

    Returns:
        SimpleBundleAnalysisResponse with analysis results
    """
    try:
        logger.info(f"Bundle analysis request received for shop: {shop_id}")

        # Initialize service
        bundle_service = BundleAnalysisService()

        # Perform analysis using the database client
        async with db as prisma_client:
            result = await bundle_service.analyze_bundles_from_database(
                prisma_client, shop_id
            )

        return result

    except Exception as e:
        logger.error(f"Unexpected error in bundle analysis endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
