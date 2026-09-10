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

    # Identity of whoever is reporting this outcome, used only to fill a blank.
    #
    # Impressions from the checkout and thank-you surfaces are written with no
    # session and no customer: those extensions get no storefront visitor id,
    # and a guest order has no customer. The clicked-then-bought reconciliation
    # joins on exactly these columns, so without them a click can be recorded
    # and never credited. Phoenix has a visitor id and sends it here when a
    # shopper arrives on a product page via a recommendation link.
    session_id: Optional[str] = Field(
        None, description="Visitor id to attach if the impression has none"
    )
    customer_id: Optional[str] = Field(
        None, description="Customer id to attach if the impression has none"
    )


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
        session_id=request.session_id,
        customer_id=request.customer_id,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to record outcome due to a server error",
        )

    return {"success": True}
