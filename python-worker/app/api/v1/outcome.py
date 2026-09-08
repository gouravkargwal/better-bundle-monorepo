"""
Outcome callback API endpoint

Called by Apollo/Mercury extensions when a user accepts or declines an offer.
Records the outcome in the offer_impressions table.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.holdout_service import HoldoutService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/interaction", tags=["outcome"])


class OutcomeRequest(BaseModel):
    impression_id: str = Field(..., description="ID of the offer impression")
    outcome: str = Field(..., pattern="^(clicked|accepted|declined|ignored)$")
    revenue_added: Optional[Decimal] = Field(
        None, description="Line-item revenue if accepted"
    )
    # 'clicked' is reported by the storefront surfaces (Phoenix, Venus), where
    # the shopper navigates to the recommended product's own page and may add
    # it there using the theme's own button — an add this app never sees. The
    # click is the last thing we can observe, so it is recorded and reconciled
    # against the order later.


@router.post("/outcome")
async def record_outcome(request: OutcomeRequest):
    """
    Record the outcome of an offer impression.
    Called by Apollo/Mercury extensions when user accepts/declines.
    """
    from app.core.database.session import get_transaction_context
    from app.core.database.models.offer_impression import OfferImpression
    from sqlalchemy import select

    # Check impression existence first to differentiate 404 from server error
    async with get_transaction_context() as session:
        result = await session.execute(
            select(OfferImpression.id).where(
                OfferImpression.id == request.impression_id
            )
        )
        impression_exists = result.scalar_one_or_none() is not None

    if not impression_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Offer impression {request.impression_id} not found",
        )

    success = await HoldoutService.record_outcome(
        impression_id=request.impression_id,
        outcome=request.outcome,
        revenue_added=request.revenue_added,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to record outcome due to a server error",
        )

    return {"success": True}
