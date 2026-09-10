"""Incrementality endpoint for the merchant dashboard.

Mirrors the shape of `edges_status.py`: one GET, a Pydantic response model,
`get_transaction_context` for the session, and errors surfaced as 500s.

Consumed by Remix through the `getEdgeStatus` proxy pattern, which degrades to
an "unavailable" state on timeout rather than failing the page. Lift is a nice
thing to know; it must never be able to take down the dashboard.
"""

from datetime import timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.lift_service import ArmSummary, LiftResult, compute_lift
from app.shared.helpers import now_utc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/impact", tags=["impact"])

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 180


class ArmResponse(BaseModel):
    shoppers: int
    converters: int
    conversion_rate: float
    revenue_per_shopper: float
    total_revenue: float
    #: Descriptive. Deliberately has no lift counterpart — AOV is conditional on
    #: converting, so a between-arm AOV difference is not a causal effect.
    aov: float

    @classmethod
    def of(cls, arm: ArmSummary) -> "ArmResponse":
        return cls(
            shoppers=arm.shoppers,
            converters=arm.converters,
            conversion_rate=arm.conversion_rate,
            revenue_per_shopper=arm.revenue_per_shopper,
            total_revenue=arm.total_revenue,
            aov=arm.aov,
        )


class LiftResponse(BaseModel):
    """Every statistic is optional and is null unless the state earned it.

    The type this replaces had non-nullable p-value and confidence-interval
    fields, so each code path was obliged to put *something* in them — which is
    how `pValue: 0.01` and a `revenue * 0.9` interval reached merchants.
    """

    shop_id: str
    window_start: str
    window_end: str
    surface: Optional[str] = None

    state: str
    treatment: ArmResponse
    control: ArmResponse
    excluded: Dict[str, int]
    surfaces_measurable: List[str]
    surfaces_not_measurable: List[str]
    min_control_orders: int
    p_value_threshold: float
    currency_code: str

    conversion_lift_abs: Optional[float] = None
    conversion_lift_rel: Optional[float] = None
    conversion_lift_rel_lower: Optional[float] = None
    conversion_lift_rel_upper: Optional[float] = None
    p_value: Optional[float] = None

    revenue_per_shopper_delta: Optional[float] = None
    revenue_delta_lower: Optional[float] = None
    revenue_delta_upper: Optional[float] = None
    revenue_p_value: Optional[float] = None

    incremental_revenue: Optional[float] = None
    incremental_revenue_lower: Optional[float] = None
    incremental_revenue_upper: Optional[float] = None


def _to_response(
    shop_id: str,
    result: LiftResult,
    start,
    end,
    surface: Optional[str],
    currency_code: str,
) -> LiftResponse:
    return LiftResponse(
        shop_id=shop_id,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        surface=surface,
        state=result.state.value,
        treatment=ArmResponse.of(result.treatment),
        control=ArmResponse.of(result.control),
        excluded=result.excluded,
        surfaces_measurable=result.surfaces_measurable,
        surfaces_not_measurable=result.surfaces_not_measurable,
        min_control_orders=result.min_control_orders,
        p_value_threshold=result.p_value_threshold,
        currency_code=currency_code,
        conversion_lift_abs=result.conversion_lift_abs,
        conversion_lift_rel=result.conversion_lift_rel,
        conversion_lift_rel_lower=result.conversion_lift_rel_lower,
        conversion_lift_rel_upper=result.conversion_lift_rel_upper,
        p_value=result.p_value,
        revenue_per_shopper_delta=result.revenue_per_shopper_delta,
        revenue_delta_lower=result.revenue_delta_lower,
        revenue_delta_upper=result.revenue_delta_upper,
        revenue_p_value=result.revenue_p_value,
        incremental_revenue=result.incremental_revenue,
        incremental_revenue_lower=result.incremental_revenue_lower,
        incremental_revenue_upper=result.incremental_revenue_upper,
    )


@router.get("/lift/{shop_id}", response_model=LiftResponse)
async def get_lift(
    shop_id: str,
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS),
    surface: Optional[str] = Query(None),
):
    """Measured incrementality for a shop, or an honest reason there is none."""
    end = now_utc()
    start = end - timedelta(days=days)

    try:
        result = await compute_lift(shop_id, start, end, surface)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Lift computation failed for {shop_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Lift computation failed")

    # Shop currency for display. Read here rather than threaded through the
    # service, which deals in one currency by construction.
    from sqlalchemy import select

    from app.core.database.models.shop import Shop
    from app.core.database.session import get_transaction_context

    async with get_transaction_context() as session:
        currency = (
            await session.execute(select(Shop.currency_code).where(Shop.id == shop_id))
        ).scalar_one_or_none()

    return _to_response(
        shop_id, result, start, end, surface, (currency or "USD").upper()
    )
