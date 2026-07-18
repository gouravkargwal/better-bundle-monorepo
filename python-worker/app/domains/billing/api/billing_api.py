"""
Simple Billing API

Consolidated billing API with essential endpoints only.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import traceback

from app.shared.helpers.datetime_utils import now_utc

from app.core.database.session import get_session_context
from app.core.database.models import (
    Shop,
    PurchaseAttribution,
)
from sqlalchemy import select, and_, func
from app.core.logging import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from ..services.billing_scheduler_service import BillingSchedulerService
from ..repositories.billing_repository_v2 import BillingPeriod, BillingRepositoryV2

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger(__name__)

# Simple auth
CRON_SECRET = "your-secret-key-here"  # TODO: Move to env


def verify_cron_secret(x_cron_secret: str = Header(None)):
    """Verify cron secret for automated endpoints"""
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# Request/Response Models
class BillingProcessRequest(BaseModel):
    shop_ids: Optional[List[str]] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    dry_run: bool = False


class BillingProcessResponse(BaseModel):
    success: bool
    processed_shops: int
    successful_shops: int
    failed_shops: int
    total_revenue: float
    total_fees: float
    errors: List[dict]


class BillingStatusResponse(BaseModel):
    status: str
    active_shops: int
    shops_with_plans: int
    pending_invoices: int
    last_updated: str


# API Endpoints
@router.post("/process", response_model=BillingProcessResponse)
async def process_billing(request: BillingProcessRequest):
    """
    Process billing for shops (manual trigger)
    """
    try:
        logger.info(f"Processing billing - dry_run={request.dry_run}")

        # Initialize scheduler service
        scheduler = BillingSchedulerService()
        await scheduler.initialize()

        # Parse period if provided
        period = None
        if request.period_start and request.period_end:
            try:
                period_start = datetime.fromisoformat(request.period_start)
                period_end = datetime.fromisoformat(request.period_end)
                period = BillingPeriod(
                    start_date=period_start, end_date=period_end, cycle="monthly"
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        # Process billing
        result = await scheduler.process_monthly_billing(
            shop_ids=request.shop_ids, period=period, dry_run=request.dry_run
        )

        return BillingProcessResponse(
            success=result.get("status") == "completed",
            processed_shops=result.get("processed_shops", 0),
            successful_shops=result.get("successful_shops", 0),
            failed_shops=result.get("failed_shops", 0),
            total_revenue=result.get("total_revenue", 0.0),
            total_fees=result.get("total_fees", 0.0),
            errors=result.get("errors", []),
        )

    except Exception as e:
        logger.error(f"Error processing billing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status():
    """
    Get billing system status
    """
    try:
        scheduler = BillingSchedulerService()
        status = await scheduler.get_billing_status()

        return BillingStatusResponse(
            status=status.get("status", "unknown"),
            active_shops=status.get("active_shops", 0),
            shops_with_plans=status.get("shops_with_billing_plans", 0),
            pending_invoices=status.get("pending_invoices", 0),
            last_updated=status.get("last_updated", now_utc().isoformat()),
        )

    except Exception as e:
        logger.error(f"Error getting billing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shop/{shop_id}/process")
async def process_shop_billing(
    shop_id: str,
    dry_run: bool = False,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
):
    """
    Process billing for a specific shop
    """
    try:
        logger.info(f"Processing billing for shop {shop_id}")

        scheduler = BillingSchedulerService()
        await scheduler.initialize()

        # Parse period if provided
        period = None
        if period_start and period_end:
            try:
                start_dt = datetime.fromisoformat(period_start)
                end_dt = datetime.fromisoformat(period_end)
                period = BillingPeriod(
                    start_date=start_dt, end_date=end_dt, cycle="monthly"
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        result = await scheduler.process_shop_billing(
            shop_id=shop_id, period=period, dry_run=dry_run
        )

        return result

    except Exception as e:
        logger.error(f"Error processing shop billing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= COMMISSION RETRIGGER / BACKFILL =============


class CommissionBackfillRequest(BaseModel):
    """Optional filters for commission backfill."""

    order_id: Optional[str] = None
    since: Optional[str] = None  # ISO8601 datetime string
    limit: Optional[int] = None  # Safety cap


class CommissionBackfillResponse(BaseModel):
    success: bool
    shop_id: str
    total_candidates: int
    events_published: int
    skipped_existing: int
    errors: List[Dict]


async def _publish_purchase_attribution_events_for_commissions(
    shop_id: str,
    order_ids: List[str],
) -> int:
    """Publish purchase_ready_for_attribution events to trigger attribution recalculation and commission creation"""
    logger.info(
        f"📤 Publishing {len(order_ids)} purchase attribution events to trigger recalculation and commission creation (shop {shop_id})"
    )

    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()

    published = 0
    failed = 0

    try:
        for i, order_id in enumerate(order_ids, 1):
            try:
                # Publish standard purchase attribution event
                # Consumer will:
                # 1. Check if line items were updated (via _is_purchase_already_processed)
                # 2. Recalculate purchase attribution if line items were updated
                # 3. Create/update commission records automatically
                event = {
                    "event_type": "purchase_ready_for_attribution",
                    "shop_id": shop_id,
                    "order_id": order_id,
                    "timestamp": now_utc().isoformat(),
                    "trigger_source": "commission_backfill_api",
                }

                await publisher.publish_purchase_attribution_event(event)
                published += 1

                if i % 10 == 0:
                    logger.info(f"📊 Progress: {i}/{len(order_ids)} events published")

            except Exception as e:
                failed += 1
                logger.error(
                    f"❌ Failed to publish event for order {order_id}: {str(e)}"
                )
                logger.error(f"   Stack trace: {traceback.format_exc()}")
                continue

        logger.info(
            f"✅ Purchase attribution events published for commission backfill (shop {shop_id})"
        )
        logger.info(f"   - Successfully published: {published}")
        logger.info(f"   - Failed events: {failed}")

    except Exception as e:
        logger.error(f"❌ Critical error publishing commission events: {str(e)}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")
        raise
    finally:
        await publisher.close()

    return published
