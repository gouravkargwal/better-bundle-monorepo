"""
Billing API

Commission reconciliation endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger(__name__)


class CommissionReconcileResponse(BaseModel):
    checked: int
    capped_reset: int
    pending_republished: int
    dry_run: bool


@router.post("/reconcile-commissions", response_model=CommissionReconcileResponse)
async def trigger_commission_reconciliation(limit: int = 100, dry_run: bool = False):
    """Trigger a commission reconciliation pass manually."""
    from ..services.commission_reconciler import reconcile_commissions_once

    try:
        result = await reconcile_commissions_once(limit=limit, dry_run=dry_run)
        return CommissionReconcileResponse(**result)
    except Exception as e:
        logger.error(f"Error in commission reconciliation endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
