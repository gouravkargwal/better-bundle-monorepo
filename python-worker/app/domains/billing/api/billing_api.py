"""
Simple Billing API

Consolidated billing API with essential endpoints only.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.shared.helpers.datetime_utils import now_utc

from app.core.database.session import get_session_context
from app.core.database.models import Shop, BillingPlan, BillingInvoice
from app.core.logging import get_logger
from ..services.billing_scheduler_service import BillingSchedulerService
from ..repositories.billing_repository import BillingPeriod

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


@router.post("/settle", response_model=BillingProcessResponse)
async def settle_daily(
    dry_run: bool = False, authorized: bool = Depends(verify_cron_secret)
):
    """
    Daily settlement (automated trigger from GitHub Actions)
    """
    try:
        logger.info(f"Starting daily settlement - dry_run={dry_run}")

        # Import settlement logic from existing file
        from .settlement_api import settle_daily_periods

        # Call existing settlement logic
        result = await settle_daily_periods(dry_run, authorized)

        return BillingProcessResponse(
            success=result.get("success", False),
            processed_shops=result.get("total_shops_checked", 0),
            successful_shops=result.get("shops_settled", 0),
            failed_shops=result.get("shops_failed", 0),
            total_revenue=result.get("total_revenue", 0.0),
            total_fees=result.get("total_commission", 0.0),
            errors=result.get("errors", []),
        )

    except Exception as e:
        logger.error(f"Error in daily settlement: {e}")
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
