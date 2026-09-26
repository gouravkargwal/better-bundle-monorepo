"""
Billing API

Commission backfill and rollover reconciliation endpoints.
"""

from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import traceback

from app.core.logging import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.shared.helpers.datetime_utils import now_utc

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger(__name__)


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


@router.post("/reconcile-rollovers")
async def trigger_rollover_reconciliation(limit: int = 50, dry_run: bool = False):
    """Trigger a rollover reconciliation pass manually."""
    from ..services.rollover_reconciler import reconcile_rollovers_once

    try:
        result = await reconcile_rollovers_once(limit=limit, dry_run=dry_run)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error in rollover reconciliation endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
