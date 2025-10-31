"""
Attribution Backfill API

Provides endpoints to retrigger purchase attribution for a shop.
Supports full-shop backfills, single-order targeting, and optional date ranges.
Enhanced with comprehensive logging and error handling.

"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
import traceback

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, desc, func

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.core.database.models import OrderData, Shop, PurchaseAttribution


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/attribution", tags=["attribution-backfill"])


class RetriggerRequest(BaseModel):
    shop_id: str = Field(..., description="Target shop ID")
    order_id: Optional[str] = Field(
        default=None, description="Optional specific order_id to target"
    )
    start: Optional[str] = Field(
        default=None, description="Optional start date (YYYY-MM-DD)"
    )
    end: Optional[str] = Field(
        default=None, description="Optional end date (YYYY-MM-DD)"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, returns counts only without publishing events",
    )


class RetriggerResponse(BaseModel):
    shop_id: str
    targeted_orders: int
    published_purchase_events: int
    dry_run: bool
    started_at: str
    success: bool = True
    message: str = "Operation completed successfully"


class ShopWideAttributionRequest(BaseModel):
    shop_id: str = Field(..., description="Target shop ID")
    force_recalculate: bool = Field(
        default=False,
        description="Force recalculation even if attribution already exists",
    )
    batch_size: int = Field(
        default=100, ge=1, le=1000, description="Number of orders to process per batch"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, returns counts only without publishing events",
    )


class ShopWideAttributionResponse(BaseModel):
    shop_id: str
    total_orders_found: int
    orders_with_existing_attribution: int
    orders_needing_attribution: int
    batches_created: int
    published_events: int
    dry_run: bool
    started_at: str
    success: bool = True
    message: str = "Shop-wide attribution trigger completed"


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str + "T00:00:00")
    except Exception:
        return None


async def _find_orders(
    shop_id: str,
    order_id: Optional[str],
    start: Optional[datetime],
    end: Optional[datetime],
) -> List[OrderData]:
    """Find orders with enhanced logging"""
    logger.info(f"🔍 Finding orders for shop {shop_id}")
    logger.info(f"   - order_id filter: {order_id}")
    logger.info(f"   - date range: {start} to {end}")

    async with get_transaction_context() as session:
        clauses = [OrderData.shop_id == shop_id]
        if order_id:
            clauses.append(OrderData.order_id == str(order_id))
        if start:
            clauses.append(OrderData.order_date >= start)
        if end:
            clauses.append(OrderData.order_date <= end)
        stmt = (
            select(OrderData).where(and_(*clauses)).order_by(desc(OrderData.order_date))
        )
        result = await session.execute(stmt)
        orders = list(result.scalars().all())

        logger.info(f"✅ Found {len(orders)} orders for shop {shop_id}")
        return orders


async def _find_shop_orders_with_attribution_status(
    shop_id: str, force_recalculate: bool = False
) -> Dict[str, Any]:
    """Find all orders for a shop and check their attribution status"""
    logger.info(f"🔍 Analyzing attribution status for shop {shop_id}")

    async with get_transaction_context() as session:
        # Get all orders for the shop
        orders_stmt = (
            select(OrderData)
            .where(OrderData.shop_id == shop_id)
            .order_by(desc(OrderData.order_date))
        )

        orders_result = await session.execute(orders_stmt)
        all_orders = list(orders_result.scalars().all())

        logger.info(f"📊 Total orders found: {len(all_orders)}")

        if not all_orders:
            return {
                "all_orders": [],
                "orders_with_attribution": [],
                "orders_needing_attribution": [],
                "total_orders": 0,
                "with_attribution": 0,
                "needing_attribution": 0,
            }

        # Get existing attributions
        order_ids = [order.order_id for order in all_orders]
        attributions_stmt = select(PurchaseAttribution).where(
            and_(
                PurchaseAttribution.shop_id == shop_id,
                PurchaseAttribution.order_id.in_(order_ids),
            )
        )
        attributions_result = await session.execute(attributions_stmt)
        existing_attributions = list(attributions_result.scalars().all())
        existing_order_ids = {attr.order_id for attr in existing_attributions}

        logger.info(f"📈 Orders with existing attribution: {len(existing_order_ids)}")

        # Determine which orders need attribution
        if force_recalculate:
            orders_needing_attribution = all_orders
            logger.info("🔄 Force recalculate enabled - all orders will be processed")
        else:
            orders_needing_attribution = [
                order
                for order in all_orders
                if order.order_id not in existing_order_ids
            ]
            logger.info(
                f"📝 Orders needing attribution: {len(orders_needing_attribution)}"
            )

        return {
            "all_orders": all_orders,
            "orders_with_attribution": [
                order for order in all_orders if order.order_id in existing_order_ids
            ],
            "orders_needing_attribution": orders_needing_attribution,
            "total_orders": len(all_orders),
            "with_attribution": len(existing_order_ids),
            "needing_attribution": len(orders_needing_attribution),
        }


async def _publish_events(
    shop_id: str,
    orders: List[OrderData],
) -> int:
    """Publish events with enhanced logging and error handling"""
    logger.info(f"📤 Starting to publish {len(orders)} events for shop {shop_id}")
    published_purchase = 0
    failed_events = 0

    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()

    try:
        for i, od in enumerate(orders, 1):
            try:
                event = {
                    "event_type": "purchase_ready_for_attribution",
                    "shop_id": shop_id,
                    "order_id": od.order_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "trigger_source": "api_attribution_backfill",
                }
                await publisher.publish_purchase_attribution_event(event)
                published_purchase += 1

                if i % 10 == 0:  # Log progress every 10 events
                    logger.info(f"📊 Progress: {i}/{len(orders)} events published")

            except Exception as e:
                failed_events += 1
                logger.error(
                    f"❌ Failed to publish event for order {od.order_id}: {str(e)}"
                )
                logger.error(f"   Stack trace: {traceback.format_exc()}")

                # Continue with other events even if one fails
                continue

        logger.info(f"✅ Event publishing completed for shop {shop_id}")
        logger.info(f"   - Successfully published: {published_purchase}")
        logger.info(f"   - Failed events: {failed_events}")

        if failed_events > 0:
            logger.warning(f"⚠️ {failed_events} events failed to publish")

    except Exception as e:
        logger.error(f"❌ Critical error in event publishing: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise
    finally:
        await publisher.close()

    return published_purchase


async def _publish_events_in_batches(
    shop_id: str, orders: List[OrderData], batch_size: int = 100
) -> int:
    """Publish events in batches with enhanced logging"""
    logger.info(f"📦 Publishing {len(orders)} events in batches of {batch_size}")

    total_published = 0
    total_batches = (len(orders) + batch_size - 1) // batch_size

    logger.info(f"📊 Total batches to process: {total_batches}")

    for batch_num in range(0, len(orders), batch_size):
        batch_orders = orders[batch_num : batch_num + batch_size]
        batch_id = (batch_num // batch_size) + 1

        logger.info(
            f"🔄 Processing batch {batch_id}/{total_batches} ({len(batch_orders)} orders)"
        )

        try:
            published_in_batch = await _publish_events(shop_id, batch_orders)
            total_published += published_in_batch

            logger.info(
                f"✅ Batch {batch_id} completed: {published_in_batch} events published"
            )

            # Small delay between batches to avoid overwhelming the system
            if batch_id < total_batches:
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"❌ Batch {batch_id} failed: {str(e)}")
            logger.error(f"   Stack trace: {traceback.format_exc()}")
            # Continue with next batch
            continue

    logger.info(f"🎉 All batches completed for shop {shop_id}")
    logger.info(f"   - Total events published: {total_published}")

    return total_published


@router.post("/retrigger", response_model=RetriggerResponse)
async def retrigger_attribution(
    request: RetriggerRequest, background_tasks: BackgroundTasks
):
    """
    Retrigger purchase attribution for a shop.

    ✅ NO REFUND COMMISSION POLICY - Only purchase attribution supported

    - order_id: target a single order; otherwise all orders in optional date range
    - start/end: date filters (inclusive). If end is set, the full day is included.
    - dry_run: return counts only without publishing events
    """
    logger.info(f"🚀 Attribution retrigger request received for shop {request.shop_id}")
    logger.info(f"   - order_id: {request.order_id}")
    logger.info(f"   - date range: {request.start} to {request.end}")
    logger.info(f"   - dry_run: {request.dry_run}")

    try:
        start = _parse_date(request.start)
        end = _parse_date(request.end)
        if end:
            end = end + timedelta(days=1) - timedelta(milliseconds=1)

        orders: List[OrderData] = await _find_orders(
            request.shop_id, request.order_id, start, end
        )

        logger.info(
            f"📊 Attribution retrigger analysis | shop_id={request.shop_id} "
            f"orders={len(orders)} dry_run={request.dry_run} "
            f"order_id={request.order_id} start={request.start} end={request.end}"
        )

        if request.dry_run:
            logger.info(f"🔍 Dry run mode - returning counts only")
            return RetriggerResponse(
                shop_id=request.shop_id,
                targeted_orders=len(orders),
                published_purchase_events=0,
                dry_run=True,
                started_at=datetime.utcnow().isoformat(),
                success=True,
                message=f"Dry run completed - {len(orders)} orders would be processed",
            )

        # Publish in the background to return immediately
        async def _run_publish():
            try:
                logger.info(
                    f"📤 Starting background attribution processing | shop_id={request.shop_id} "
                    f"purchase_events={len(orders)}"
                )
                published_purchase = await _publish_events(request.shop_id, orders)
                logger.info(
                    f"✅ Background attribution processing completed | shop_id={request.shop_id} "
                    f"purchase_events={published_purchase}"
                )
            except Exception as e:
                logger.error(f"❌ Background attribution processing failed: {e}")
                logger.error(f"   Stack trace: {traceback.format_exc()}")

        background_tasks.add_task(_run_publish)

        return RetriggerResponse(
            shop_id=request.shop_id,
            targeted_orders=len(orders),
            published_purchase_events=0,
            dry_run=False,
            started_at=datetime.utcnow().isoformat(),
            success=True,
            message=f"Attribution processing started for {len(orders)} orders",
        )

    except Exception as e:
        logger.error(f"❌ Attribution retrigger failed: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Attribution retrigger failed: {str(e)}"
        )


@router.post("/shop-wide", response_model=ShopWideAttributionResponse)
async def trigger_shop_wide_attribution(
    request: ShopWideAttributionRequest, background_tasks: BackgroundTasks
):
    """
    🎯 Shop-wide purchase attribution trigger

    This endpoint triggers purchase attribution recalculation for ALL orders in a shop.
    It's designed to handle cases where attribution might have been missed.

    Features:
    - Analyzes existing attribution status
    - Processes only orders that need attribution (unless force_recalculate=True)
    - Batch processing for large shops
    - Comprehensive logging and error handling
    - Dry run mode for testing
    """
    try:
        # Analyze shop's attribution status
        attribution_analysis = await _find_shop_orders_with_attribution_status(
            request.shop_id, request.force_recalculate
        )

        orders_needing_attribution = attribution_analysis["orders_needing_attribution"]
        total_orders = attribution_analysis["total_orders"]
        with_attribution = attribution_analysis["with_attribution"]
        needing_attribution = attribution_analysis["needing_attribution"]

        logger.info(f"📊 Shop attribution analysis completed:")
        logger.info(f"   - Total orders: {total_orders}")
        logger.info(f"   - Orders with attribution: {with_attribution}")
        logger.info(f"   - Orders needing attribution: {needing_attribution}")

        if not orders_needing_attribution:
            logger.info(
                f"✅ No orders need attribution processing for shop {request.shop_id}"
            )
            return ShopWideAttributionResponse(
                shop_id=request.shop_id,
                total_orders_found=total_orders,
                orders_with_existing_attribution=with_attribution,
                orders_needing_attribution=0,
                batches_created=0,
                published_events=0,
                dry_run=request.dry_run,
                started_at=datetime.utcnow().isoformat(),
                success=True,
                message="No orders need attribution processing",
            )

        # Calculate batches
        batch_size = request.batch_size
        total_batches = (len(orders_needing_attribution) + batch_size - 1) // batch_size

        logger.info(f"📦 Processing plan:")
        logger.info(f"   - Orders to process: {len(orders_needing_attribution)}")
        logger.info(f"   - Batch size: {batch_size}")
        logger.info(f"   - Total batches: {total_batches}")

        if request.dry_run:
            logger.info(f"🔍 Dry run mode - returning analysis only")
            return ShopWideAttributionResponse(
                shop_id=request.shop_id,
                total_orders_found=total_orders,
                orders_with_existing_attribution=with_attribution,
                orders_needing_attribution=needing_attribution,
                batches_created=total_batches,
                published_events=0,
                dry_run=True,
                started_at=datetime.utcnow().isoformat(),
                success=True,
                message=f"Dry run completed - {needing_attribution} orders would be processed in {total_batches} batches",
            )

        # Process in background
        async def _run_shop_wide_processing():
            try:
                logger.info(
                    f"🚀 Starting shop-wide attribution processing for {request.shop_id}"
                )
                published_events = await _publish_events_in_batches(
                    request.shop_id, orders_needing_attribution, request.batch_size
                )
                logger.info(
                    f"🎉 Shop-wide attribution processing completed for {request.shop_id}"
                )
                logger.info(f"   - Total events published: {published_events}")
            except Exception as e:
                logger.error(f"❌ Shop-wide attribution processing failed: {e}")
                logger.error(f"   Stack trace: {traceback.format_exc()}")

        background_tasks.add_task(_run_shop_wide_processing)

        return ShopWideAttributionResponse(
            shop_id=request.shop_id,
            total_orders_found=total_orders,
            orders_with_existing_attribution=with_attribution,
            orders_needing_attribution=needing_attribution,
            batches_created=total_batches,
            published_events=0,  # Will be updated in background
            dry_run=False,
            started_at=datetime.utcnow().isoformat(),
            success=True,
            message=f"Shop-wide attribution processing started for {needing_attribution} orders in {total_batches} batches",
        )

    except Exception as e:
        logger.error(f"❌ Shop-wide attribution trigger failed: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Shop-wide attribution trigger failed: {str(e)}"
        )


@router.get("/status/{shop_id}")
async def get_attribution_status(shop_id: str):
    """
    📊 Get attribution status for a shop

    Returns detailed information about attribution coverage for a shop.
    """
    logger.info(f"📊 Attribution status requested for shop {shop_id}")

    try:
        attribution_analysis = await _find_shop_orders_with_attribution_status(
            shop_id, False
        )

        return {
            "shop_id": shop_id,
            "total_orders": attribution_analysis["total_orders"],
            "orders_with_attribution": attribution_analysis["with_attribution"],
            "orders_needing_attribution": attribution_analysis["needing_attribution"],
            "attribution_coverage_percentage": round(
                (
                    attribution_analysis["with_attribution"]
                    / max(attribution_analysis["total_orders"], 1)
                )
                * 100,
                2,
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to get attribution status: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get attribution status: {str(e)}"
        )
