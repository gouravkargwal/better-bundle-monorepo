"""
Holdout Service for Incrementality Testing

Determines whether a session should be held out (no offer shown) and logs
impressions/outcomes to the offer_impressions table.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.core.database.session import get_transaction_context
from app.core.database.models.offer_impression import OfferImpression
from app.core.database.models.shop import Shop
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default holdout percentage
INITIAL_HOLDOUT_PERCENT = 10  # 10% initially
SENTINEL_HOLDOUT_PERCENT = 2   # 2% after significance reached
MIN_CONTROL_ORDERS = 100       # minimum control orders before reporting
P_VALUE_THRESHOLD = 0.05       # significance threshold

# Per-surface overrides. A surface absent here uses INITIAL_HOLDOUT_PERCENT.
#
# Checkout and thank-you are held at 0 deliberately, not by oversight. They only
# became bucketable at all once the `_bb_session` cart attribute gave them a
# stable identity, and that arrived long before they had the traffic to measure.
# A 10% holdout across 21 impressions is about two control sessions — no
# statistical signal whatsoever — bought by withholding offers from shoppers who
# were already at the payment step. That is the worst possible trade: real
# forgone revenue for noise.
#
# The capability is in place; only the number is off. Raise these once the
# surface is doing enough volume to clear MIN_CONTROL_ORDERS in reasonable time,
# and the experiment starts with no further code change.
SURFACE_HOLDOUT_PERCENT = {
    "mercury": 0,
    "thank_you": 0,
}


class HoldoutService:
    """
    Handles holdout bucketing and offer_impressions logging.
    """

    @staticmethod
    def get_holdout_percent(shop: Shop, surface: Optional[str] = None) -> int:
        """The holdout percentage for this shop and surface.

        The merchant's own switch wins over everything: `holdout_disabled` means
        no shopper is ever withheld an offer, on any surface.

        Otherwise a surface may set its own rate — see SURFACE_HOLDOUT_PERCENT
        for why checkout and thank-you are currently zero. Surfaces not listed
        get the shop-wide default.

        `surface` is optional so existing callers keep working; passing None
        gives the shop-wide rate.
        """
        if shop.holdout_disabled:
            return 0

        if surface is not None and surface in SURFACE_HOLDOUT_PERCENT:
            return SURFACE_HOLDOUT_PERCENT[surface]

        # Future: read from a shop config or derive from rollup stats.
        return INITIAL_HOLDOUT_PERCENT

    @staticmethod
    def is_held_out(
        shop_id: str,
        customer_id: Optional[str],
        session_id: Optional[str],
        holdout_percent: int,
    ) -> bool:
        """
        Deterministically decide if this shopper is in the control group.

        Buckets on a stable hash of shop_id plus the shopper's identity, so the
        same shopper always gets the same treatment and the control group stays
        a clean counterfactual.

        Identity is `customer_id` when known, otherwise the client-generated
        visitor id passed as `session_id`. With neither, bucketing is impossible
        and this returns False: every anonymous shopper would otherwise hash to
        the SAME bucket, meaning either all of them are held out — the widget
        never renders and the merchant sees a dead app — or none of them are.
        Declining to hold out is the safe half of that failure, and the missing
        id is logged so it does not stay silent.
        """
        if holdout_percent <= 0:
            return False

        identity = customer_id or session_id
        if not identity:
            # Expected whenever a shopper has declined measurement consent, so
            # this is routine rather than a fault. Such shoppers still receive
            # recommendations; they are excluded from the lift calculation by
            # the `bucketed: false` flag the caller records on the impression.
            logger.debug(
                f"Holdout skipped for shop {shop_id}: no stable identity, "
                f"shopper excluded from the experiment"
            )
            return False

        key = f"{shop_id}:{identity}"
        bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        return bucket < holdout_percent

    @staticmethod
    async def log_impression(
        shop_id: str,
        surface: str,
        offer_type: str,
        is_control: bool,
        session_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        offer_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        outcome: str = "shown",
        metadata: Optional[dict] = None,
        impression_group_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log an offer impression. Returns the impression_id for outcome callbacks.
        """
        try:
            impression_id = str(uuid.uuid4())
            impression = OfferImpression(
                id=impression_id,
                shop_id=shop_id,
                session_id=session_id,
                customer_id=customer_id,
                surface=surface,
                offer_type=offer_type,
                offer_id=offer_id,
                variant_id=variant_id,
                is_control=is_control,
                outcome=outcome,
                offer_metadata=metadata or {},
                impression_group_id=impression_group_id or str(uuid.uuid4()),
            )

            async with get_transaction_context() as session:
                session.add(impression)

            return impression_id
        except Exception as e:
            logger.error(f"Failed to log offer impression: {e}")
            return None

    @staticmethod
    async def record_outcome(
        impression_id: str,
        outcome: str,
        revenue_added: Optional[Decimal] = None,
        session_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> bool:
        """
        Record the outcome of an offer impression (clicked/accepted/declined/ignored).

        `session_id` / `customer_id` backfill an identity the impression was
        written without. This is what makes a click-through billable at all:
        the checkout and thank-you surfaces have no storefront visitor id and no
        customer on a guest order, so their impressions are written with both
        columns NULL. The clicked-then-bought path joins the impression to a
        later order on exactly those columns, and `NULL = anything` never
        matches — so before this, every thank-you click was recorded and then
        could never be credited.

        Only ever fills a blank. An impression that already carries an identity
        keeps it: overwriting would let a second shopper's click reassign the
        first shopper's offer, and the holdout bucket that identity was drawn
        from would no longer match the arm the impression was recorded in.
        """
        try:
            async with get_transaction_context() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(OfferImpression).where(OfferImpression.id == impression_id)
                )
                impression = result.scalar_one_or_none()
                if not impression:
                    logger.warning(f"OfferImpression {impression_id} not found for outcome")
                    return False
                impression.outcome = outcome
                impression.outcome_at = datetime.now(timezone.utc)
                if revenue_added is not None:
                    impression.revenue_added = revenue_added
                if session_id and not impression.session_id:
                    impression.session_id = session_id
                if customer_id and not impression.customer_id:
                    impression.customer_id = customer_id
            return True
        except Exception as e:
            logger.error(f"Failed to record outcome for {impression_id}: {e}")
            return False

    @staticmethod
    async def log_control_session(
        shop_id: str,
        surface: str,
        session_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        impression_group_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a control-group session (no offer shown)."""
        return await HoldoutService.log_impression(
            shop_id=shop_id,
            surface=surface,
            offer_type="control",
            is_control=True,
            session_id=session_id,
            customer_id=customer_id,
            metadata=metadata,
            impression_group_id=impression_group_id,
        )
