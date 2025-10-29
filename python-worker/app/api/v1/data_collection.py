"""
Data Collection API

Provides endpoints to trigger data collection for shops.
Supports full data collection, specific data types, and date ranges.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
import traceback

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.database.models import Shop
from app.domains.shopify.services.data_collection import ShopifyDataCollectionService
from app.shared.helpers import now_utc

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/data-collection", tags=["data-collection"])


class DataCollectionRequest(BaseModel):
    shop_id: str = Field(..., description="Target shop ID")
    data_types: Optional[List[str]] = Field(
        default=None,
        description="Specific data types to collect (orders, products, customers). If None, collects all.",
    )
    since_hours: Optional[int] = Field(
        default=24, description="Hours back to collect data from (default: 24)"
    )
    force_refresh: bool = Field(
        default=False, description="Force refresh even if data was recently collected"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, returns counts only without collecting data",
    )


class DataCollectionResponse(BaseModel):
    shop_id: str
    success: bool
    data_types_collected: List[str]
    orders_collected: int
    products_collected: int
    customers_collected: int
    collection_duration: float
    timestamp: str
    message: str
    errors: List[str] = []


@router.post("/trigger", response_model=DataCollectionResponse)
async def trigger_data_collection(
    request: DataCollectionRequest, background_tasks: BackgroundTasks
):
    """
    🚀 Trigger data collection for a shop

    This endpoint triggers data collection from Shopify for the specified shop.
    It can collect orders, products, customers, or all data types.

    Features:
    - Collects data from Shopify API
    - Supports specific data types or all data
    - Date range filtering
    - Force refresh option
    - Dry run mode for testing
    """
    logger.info(f"🚀 Data collection trigger requested for shop {request.shop_id}")
    logger.info(f"   - data_types: {request.data_types}")
    logger.info(f"   - since_hours: {request.since_hours}")
    logger.info(f"   - force_refresh: {request.force_refresh}")
    logger.info(f"   - dry_run: {request.dry_run}")

    start_time = now_utc()
    errors = []

    try:
        # Get shop data
        async with get_transaction_context() as session:
            from sqlalchemy import select

            shop_query = select(Shop).where(Shop.id == request.shop_id)
            result = await session.execute(shop_query)
            shop = result.scalar_one_or_none()

            if not shop:
                raise HTTPException(
                    status_code=404, detail=f"Shop {request.shop_id} not found"
                )

            if not shop.is_active:
                raise HTTPException(
                    status_code=400, detail=f"Shop {request.shop_id} is not active"
                )

        # Prepare collection payload
        collection_payload = {
            "data_types": request.data_types or ["orders", "products", "customers"],
            "since_hours": request.since_hours,
            "force_refresh": request.force_refresh,
            "dry_run": request.dry_run,
        }

        if request.dry_run:
            # Dry run - just return what would be collected
            logger.info(f"🔍 Dry run mode - would collect: {collection_payload}")
            return DataCollectionResponse(
                shop_id=request.shop_id,
                success=True,
                data_types_collected=collection_payload["data_types"],
                orders_collected=0,
                products_collected=0,
                customers_collected=0,
                collection_duration=0.0,
                timestamp=now_utc().isoformat(),
                message="Dry run completed - no data collected",
                errors=[],
            )

        # Initialize data collection service with required dependencies
        from app.domains.shopify.services import (
            ShopifyAPIClient,
            ShopifyPermissionService,
        )

        api_client = ShopifyAPIClient()
        permission_service = ShopifyPermissionService(api_client=api_client)
        data_collection_service = ShopifyDataCollectionService(
            api_client=api_client, permission_service=permission_service
        )

        # Trigger data collection
        result = await data_collection_service.collect_all_data(
            shop_domain=shop.shop_domain,
            access_token=shop.access_token,
            shop_id=shop.id,
            collection_payload=collection_payload,
        )

        # Calculate duration
        duration = (now_utc() - start_time).total_seconds()

        # Extract results
        orders_collected = result.get("orders_collected", 0)
        products_collected = result.get("products_collected", 0)
        customers_collected = result.get("customers_collected", 0)

        logger.info(f"✅ Data collection completed for shop {request.shop_id}")
        logger.info(f"   - Orders: {orders_collected}")
        logger.info(f"   - Products: {products_collected}")
        logger.info(f"   - Customers: {customers_collected}")
        logger.info(f"   - Duration: {duration:.2f}s")

        return DataCollectionResponse(
            shop_id=request.shop_id,
            success=True,
            data_types_collected=collection_payload["data_types"],
            orders_collected=orders_collected,
            products_collected=products_collected,
            customers_collected=customers_collected,
            collection_duration=duration,
            timestamp=now_utc().isoformat(),
            message=f"Successfully collected data: {orders_collected} orders, {products_collected} products, {customers_collected} customers",
            errors=[],
        )

    except Exception as e:
        error_msg = f"Data collection failed for shop {request.shop_id}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())

        errors.append(error_msg)

        return DataCollectionResponse(
            shop_id=request.shop_id,
            success=False,
            data_types_collected=request.data_types or [],
            orders_collected=0,
            products_collected=0,
            customers_collected=0,
            collection_duration=(now_utc() - start_time).total_seconds(),
            timestamp=now_utc().isoformat(),
            message=f"Data collection failed: {str(e)}",
            errors=errors,
        )


@router.get("/status/{shop_id}")
async def get_collection_status(shop_id: str):
    """
    Get data collection status for a shop
    """
    try:
        async with get_transaction_context() as session:
            from sqlalchemy import select

            shop_query = select(Shop).where(Shop.id == shop_id)
            result = await session.execute(shop_query)
            shop = result.scalar_one_or_none()

            if not shop:
                raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        # Get recent collection stats (this would need to be implemented based on your logging/storage)
        return {
            "shop_id": shop_id,
            "shop_domain": shop.shop_domain,
            "is_active": shop.is_active,
            "last_collection": "Not implemented yet",  # Would need to track this
            "status": "ready" if shop.is_active else "inactive",
        }

    except Exception as e:
        logger.error(f"Failed to get collection status for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
