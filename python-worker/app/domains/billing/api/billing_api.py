"""
Simple Billing API

Consolidated billing API with essential endpoints only.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.shared.helpers.datetime_utils import now_utc

from app.core.database.session import get_session_context
from app.core.database.models import (
    Shop,
    BillingPlan,
    BillingInvoice,
    PurchaseAttribution,
    CommissionRecord,
)
from sqlalchemy import select, and_
from app.core.logging import get_logger
from ..services.billing_scheduler_service import BillingSchedulerService
from ..repositories.billing_repository import BillingPeriod
from ..services.commission_service import CommissionService

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
    created: int
    skipped_existing: int
    errors: List[Dict]


@router.post(
    "/shop/{shop_id}/retrigger-commissions", response_model=CommissionBackfillResponse
)
async def retrigger_commissions(shop_id: str, request: CommissionBackfillRequest):
    """
    Create missing commission records for a shop by scanning `purchase_attributions`.
    - Idempotent: existing commissions are skipped
    - Optional filters: specific `order_id`, `since` timestamp, and `limit`
    """
    try:
        logger.info(
            f"[commission-backfill] Start - shop_id={shop_id}, order_id={request.order_id}, "
            f"since={request.since}, limit={request.limit}"
        )
        async with get_session_context() as session:
            # Build base query
            stmt = select(PurchaseAttribution.id).where(
                PurchaseAttribution.shop_id == shop_id
            )

            # Filter by order_id if provided
            if request.order_id:
                stmt = stmt.where(PurchaseAttribution.order_id == request.order_id)

            # Filter by since if provided
            if request.since:
                try:
                    since_dt = datetime.fromisoformat(request.since)
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid 'since' format. Use ISO8601."
                    )
                stmt = stmt.where(PurchaseAttribution.created_at >= since_dt)

            # Apply a safety limit if provided
            if request.limit and request.limit > 0:
                stmt = stmt.limit(request.limit)

            logger.debug(f"[commission-backfill] Query built: {stmt}")
            res = await session.execute(stmt)
            attribution_ids = [str(x) for x in res.scalars().all()]

            total_candidates = len(attribution_ids)
            logger.info(f"[commission-backfill] Candidates fetched: {total_candidates}")
            if total_candidates == 0:
                return CommissionBackfillResponse(
                    success=True,
                    shop_id=shop_id,
                    total_candidates=0,
                    created=0,
                    skipped_existing=0,
                    errors=[],
                )

            # Find existing commissions
            existing_q = select(CommissionRecord.purchase_attribution_id).where(
                CommissionRecord.purchase_attribution_id.in_(attribution_ids)
            )
            logger.debug(f"[commission-backfill] Existing check query: {existing_q}")
            existing_res = await session.execute(existing_q)
            existing_ids = {str(x) for x in existing_res.scalars().all()}

            to_create = [pid for pid in attribution_ids if pid not in existing_ids]
            logger.info(
                f"[commission-backfill] Existing: {len(existing_ids)}, Missing: {len(to_create)}"
            )

            service = CommissionService(session)
            created = 0
            errors: List[Dict] = []
            for pid in to_create:
                try:
                    logger.debug(
                        f"[commission-backfill] Creating commission for attribution_id={pid}"
                    )
                    commission = await service.create_commission_record(
                        purchase_attribution_id=pid, shop_id=shop_id
                    )
                    if commission:
                        created += 1
                        logger.debug(
                            f"[commission-backfill] Created commission id={commission.id} for attribution_id={pid}"
                        )
                except Exception as e:  # pragma: no cover
                    errors.append({"purchase_attribution_id": pid, "error": str(e)})
                    logger.error(
                        f"[commission-backfill] Error creating commission for attribution_id={pid}: {e}"
                    )

            response = CommissionBackfillResponse(
                success=len(errors) == 0,
                shop_id=shop_id,
                total_candidates=total_candidates,
                created=created,
                skipped_existing=len(existing_ids),
                errors=errors,
            )
            logger.info(
                f"[commission-backfill] Done - created={created}, skipped={len(existing_ids)}, "
                f"errors={len(errors)}"
            )
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retriggering commissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
