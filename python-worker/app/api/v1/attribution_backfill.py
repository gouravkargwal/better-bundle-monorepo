"""
Attribution Backfill API

Provides an endpoint to retrigger purchase and/or refund attribution for a shop.
Supports full-shop backfills, single-order targeting, and optional date ranges.
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, desc

from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.core.database.models import OrderData, RefundData


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/attribution", tags=["attribution-backfill"])


class RetriggerRequest(BaseModel):
    shop_id: str = Field(..., description="Target shop ID")
    scope: str = Field(
        default="both", description="What to retrigger: purchase | refund | both"
    )
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
    scope: str
    targeted_orders: int
    targeted_refunds: int
    published_purchase_events: int
    published_refund_events: int
    dry_run: bool
    started_at: str


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
        return list(result.scalars().all())


async def _find_refunds(
    shop_id: str,
    order_id: Optional[str],
    start: Optional[datetime],
    end: Optional[datetime],
) -> List[RefundData]:
    async with get_transaction_context() as session:
        clauses = [RefundData.shop_id == shop_id]
        if order_id:
            clauses.append(RefundData.order_id == str(order_id))
        if start:
            clauses.append(RefundData.refunded_at >= start)
        if end:
            clauses.append(RefundData.refunded_at <= end)
        stmt = (
            select(RefundData)
            .where(and_(*clauses))
            .order_by(desc(RefundData.refunded_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _publish_events(
    shop_id: str,
    orders: List[OrderData],
    refunds: List[RefundData],
) -> (int, int):
    published_purchase = 0
    published_refund = 0

    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()
    try:
        # Purchase events
        for od in orders:
            event = {
                "event_type": "purchase_ready_for_attribution",
                "shop_id": shop_id,
                "order_id": od.order_id,
                "timestamp": datetime.utcnow().isoformat(),
                "trigger_source": "api_attribution_backfill",
            }
            await publisher.publish_purchase_attribution_event(event)
            published_purchase += 1

        # Refund events
        for rd in refunds:
            event = {
                "event_type": "refund_created",
                "shop_id": shop_id,
                "order_id": rd.order_id,
                "refund_id": rd.refund_id,
                "timestamp": datetime.utcnow().isoformat(),
                "trigger_source": "api_attribution_backfill",
            }
            await publisher.publish_refund_attribution_event(event)
            published_refund += 1

    finally:
        await publisher.close()

    return published_purchase, published_refund


@router.post("/retrigger", response_model=RetriggerResponse)
async def retrigger_attribution(
    request: RetriggerRequest, background_tasks: BackgroundTasks
):
    """
    Retrigger purchase and/or refund attribution for a shop.

    - scope: purchase | refund | both
    - order_id: target a single order; otherwise all orders in optional date range
    - start/end: date filters (inclusive). If end is set, the full day is included.
    - dry_run: return counts only without publishing events
    """
    if request.scope not in {"purchase", "refund", "both"}:
        raise HTTPException(status_code=400, detail="Invalid scope")

    start = _parse_date(request.start)
    end = _parse_date(request.end)
    if end:
        end = end + timedelta(days=1) - timedelta(milliseconds=1)

    orders: List[OrderData] = []
    refunds: List[RefundData] = []

    if request.scope in ("purchase", "both"):
        orders = await _find_orders(request.shop_id, request.order_id, start, end)
    if request.scope in ("refund", "both"):
        refunds = await _find_refunds(request.shop_id, request.order_id, start, end)

    logger.info(
        f"Attribution backfill requested | shop_id={request.shop_id} scope={request.scope} "
        f"orders={len(orders)} refunds={len(refunds)} dry_run={request.dry_run} "
        f"order_id={request.order_id} start={request.start} end={request.end}"
    )

    if request.dry_run:
        return RetriggerResponse(
            shop_id=request.shop_id,
            scope=request.scope,
            targeted_orders=len(orders),
            targeted_refunds=len(refunds),
            published_purchase_events=0,
            published_refund_events=0,
            dry_run=True,
            started_at=datetime.utcnow().isoformat(),
        )

    # Publish in the background to return immediately
    async def _run_publish():
        try:
            logger.info(
                f"Publishing attribution events | shop_id={request.shop_id} "
                f"purchase_events={len(orders)} refund_events={len(refunds)}"
            )
            published_purchase, published_refund = await _publish_events(
                request.shop_id, orders, refunds
            )
            logger.info(
                f"Published attribution events | shop_id={request.shop_id} "
                f"purchase_events={published_purchase} refund_events={published_refund}"
            )
        except Exception as e:
            logger.error(f"Failed to publish attribution events: {e}")

    background_tasks.add_task(_run_publish)

    return RetriggerResponse(
        shop_id=request.shop_id,
        scope=request.scope,
        targeted_orders=len(orders),
        targeted_refunds=len(refunds),
        published_purchase_events=0,
        published_refund_events=0,
        dry_run=False,
        started_at=datetime.utcnow().isoformat(),
    )
