"""
Attribution Engine for Billing System

Attribution is *measured*, not inferred.

Every recommendation served to a treatment-group shopper writes an
`offer_impressions` row and hands the extension back its `impression_id`. When
the shopper accepts the offer, the extension reports the outcome and the revenue
it added, and `HoldoutService.record_outcome` writes both onto that row. The
impression row is therefore already the attribution record: this engine only has
to collect the accepted impressions belonging to an order and total them.

That replaces ~1,900 lines of multi-touch journey reconstruction, time-decay
weighting and confidence scoring built on the `user_interactions` table, which
has had no writer since the behaviour-tracking pipeline was removed.

Two invariants matter for billing correctness:

1. **Control impressions are never attributable.** A held-out shopper was shown
   no offer, so no revenue can be credited to one.
2. **Never attribute blind.** If an order carries no session or customer we can
   join on, attributed revenue is zero. Guessing here bills a merchant for
   revenue we did not influence.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.helpers import now_utc
from app.core.database.models import PurchaseAttribution
from app.core.database.models.offer_impression import OfferImpression
from app.core.database.session import get_session_context

from ..models.attribution_models import (
    AttributionResult,
    AttributionBreakdown,
    AttributionType,
    AttributionStatus,
    ExtensionType,
)

logger = logging.getLogger(__name__)


# An offer is shown inside the checkout or on the thank-you page, so the
# impression lands within minutes of the order. The window is generous rather
# than tight because a post-purchase impression is created *after* the order
# exists, which is why it is two-sided.
ATTRIBUTION_WINDOW_BEFORE = timedelta(hours=24)
ATTRIBUTION_WINDOW_AFTER = timedelta(hours=24)

# Click-to-purchase spans sessions and days, so this window is wider than the
# in-the-moment one. Seven days is the common e-commerce default; longer starts
# crediting purchases the recommendation plausibly had nothing to do with.
CLICK_ATTRIBUTION_WINDOW = timedelta(days=7)

# Namespace Mercury writes onto the cart, which Shopify promotes to the order.
TRACKING_NAMESPACE = "bb_recommendation"

# Line-item property carrying the impression a recommendation came from.
#
# This is how the *storefront* surfaces attribute. Checkout and post-purchase
# offers are accepted in the moment, so their extension can report the outcome
# and the revenue synchronously. A product-page recommendation cannot: the
# shopper clicks through, browses, and may buy an hour or a week later, long
# after the widget is gone. So Phoenix and Venus stamp the impression id onto
# the cart line instead, Shopify promotes it to the order line, and the paid
# order line *is* the acceptance.
#
# Read from `line_item_data.properties`, populated by the order normalizer.
LINE_ITEM_IMPRESSION_KEY = "_bb_rec_impression_id"

# `offer_impressions.surface` is already the extension name.
# Every surface the recommendation API can serve. A surface missing here is
# not a warning that degrades quality — it is revenue that cannot be billed,
# because _build_breakdown skips any impression it cannot map. Keep this in
# step with CONTEXT_SURFACE in api/v1/recommendations.py.
_SURFACE_TO_EXTENSION = {
    "mercury": ExtensionType.MERCURY,
    "apollo": ExtensionType.APOLLO,
    "phoenix": ExtensionType.PHOENIX,
    "venus": ExtensionType.VENUS,
    # The thank-you block is part of the mercury extension, not a separate
    # one — same bundle, second placement. The placement stays distinguishable
    # through offer_impressions.surface.
    "thank_you": ExtensionType.MERCURY,
}


@dataclass
class AttributionContext:
    """Context for attribution calculation"""

    shop_id: str
    customer_id: Optional[str]
    session_id: Optional[str]
    order_id: str
    purchase_amount: Decimal
    purchase_products: List[Dict[str, Any]]
    purchase_time: datetime
    order_metafields: Optional[List[Dict[str, Any]]] = None


class AttributionEngine:
    """Totals the accepted offer impressions that belong to an order."""

    def __init__(self, session: AsyncSession = None):
        self.session = session

    # ---------- public API ----------

    async def calculate_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """Calculate attribution for a purchase event."""
        try:
            # Never bill on money that did not actually change hands.
            if await self._is_payment_failed(context):
                logger.warning(
                    f"⚠️ Payment failed for order {context.order_id} - skipping attribution"
                )
                result = self._create_rejected_attribution(
                    context, "payment_failed", "Payment failed - no attribution given"
                )
                await self._store_attribution_result(result)
                return result

            if await self._is_subscription_cancelled(context):
                logger.warning(
                    f"📋 Subscription cancelled for order {context.order_id}"
                )
                result = self._create_rejected_attribution(
                    context, "subscription_cancelled", "Subscription cancelled"
                )
                await self._store_attribution_result(result)
                return result

            impressions = await self._get_accepted_impressions(context)
            if not impressions:
                result = self._create_empty_attribution(context)
                await self._store_attribution_result(result)
                return result

            breakdown = self._build_breakdown(context, impressions)
            total = sum((b.attributed_amount for b in breakdown), Decimal("0.00"))

            result = AttributionResult(
                order_id=context.order_id,
                shop_id=context.shop_id,
                customer_id=context.customer_id,
                session_id=self._link_session_id(context),
                total_attributed_revenue=total,
                attribution_breakdown=breakdown,
                attribution_type=AttributionType.DIRECT_CLICK,
                status=AttributionStatus.CALCULATED,
                calculated_at=now_utc(),
                metadata={
                    "method": "offer_impressions",
                    "accepted_impressions": len(impressions),
                    "attributed_impressions": len(breakdown),
                },
            )
            # The row id is what billing keys the commission off, so surface it
            # rather than discarding it — one commission per attribution.
            attribution_id = await self._store_attribution_result(result)
            result.metadata["purchase_attribution_id"] = attribution_id
            logger.info(
                f"✅ Attribution for order {context.order_id}: {total} across "
                f"{len(breakdown)} accepted offers"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ Attribution failed for order {context.order_id}: {e}",
                exc_info=True,
            )
            raise

    # ---------- impression collection ----------

    def _link_session_id(self, context: AttributionContext) -> Optional[str]:
        """The session to join impressions on.

        Mercury stamps the session onto the cart, which Shopify promotes to the
        order, so the metafield is more trustworthy than whatever the caller
        happened to pass in.
        """
        for mf in context.order_metafields or []:
            if (
                mf.get("namespace") == TRACKING_NAMESPACE
                and mf.get("key") == "session_id"
                and mf.get("value")
            ):
                return str(mf["value"])
        return context.session_id

    def _impression_ids_from_line_items(
        self, context: AttributionContext
    ) -> Dict[str, Dict[str, Any]]:
        """Impression ids stamped onto the order's own line items.

        Returns impression_id -> the line item carrying it, so the line's own
        price can be used as the attributed amount.
        """
        found: Dict[str, Dict[str, Any]] = {}
        for product in context.purchase_products or []:
            props = product.get("properties") or {}
            if not isinstance(props, dict):
                continue
            iid = props.get(LINE_ITEM_IMPRESSION_KEY)
            if iid:
                found[str(iid)] = product
        return found

    async def _get_accepted_impressions(
        self, context: AttributionContext
    ) -> List[OfferImpression]:
        """Impressions this order can be credited to.

        Two independent paths, unioned:

        1. **Line-item stamped** — the order itself carries the impression id.
           These are attributable regardless of the impression's `outcome`
           column, because a paid order line carrying the stamp is stronger
           evidence than any callback. The storefront surfaces rely on this
           entirely: nothing reports their outcome in the moment.

        2. **Outcome-reported** — the extension called back with
           `outcome='accepted'` and a revenue figure. Checkout and
           post-purchase offers work this way.

        3. **Clicked, then bought** — the shopper clicked a storefront
           recommendation, navigated to that product's own page, and added it
           with the theme's own button. This app never sees that add, so no
           stamp exists. What we do know is the exact product we recommended
           (`offer_id`), so if it appears in a paid order inside the window,
           the click is credited.

           Path 3 will over-credit: some of those shoppers would have bought
           the product anyway. That is precisely what the held-out control
           group corrects. Per-order attribution is the upper bound; the
           treatment-minus-control difference is the number to bill on.

        Control impressions are excluded from both. A held-out shopper was
        shown no offer, so a stamp on their order would be a bug, not revenue.
        """
        stamped = self._impression_ids_from_line_items(context)
        session_id = self._link_session_id(context)

        links = []
        if session_id:
            links.append(OfferImpression.session_id == session_id)
        if context.customer_id:
            links.append(OfferImpression.customer_id == context.customer_id)

        clauses = []

        # Path 1: stamped on the order. No time window and no outcome filter —
        # the stamp travelled on the cart, so it is self-evidencing however long
        # the shopper took to buy.
        if stamped:
            clauses.append(OfferImpression.id.in_(list(stamped)))

        # Path 2: reported by an extension in the moment.
        if links:
            clauses.append(
                and_(
                    OfferImpression.outcome == "accepted",
                    OfferImpression.created_at
                    >= context.purchase_time - ATTRIBUTION_WINDOW_BEFORE,
                    OfferImpression.created_at
                    <= context.purchase_time + ATTRIBUTION_WINDOW_AFTER,
                    or_(*links),
                )
            )

        # Path 3: clicked, then bought via the theme's own button. Matched on
        # the recommended product actually appearing in the order, which is an
        # exact match rather than a heuristic, over a longer window because
        # click-to-purchase spans sessions.
        purchased_ids = {
            str(p.get("product_id") or p.get("id") or "")
            for p in (context.purchase_products or [])
        }
        purchased_ids.discard("")
        if links and purchased_ids:
            clauses.append(
                and_(
                    OfferImpression.outcome == "clicked",
                    OfferImpression.offer_id.in_(sorted(purchased_ids)),
                    OfferImpression.created_at
                    >= context.purchase_time - CLICK_ATTRIBUTION_WINDOW,
                    OfferImpression.created_at <= context.purchase_time,
                    or_(*links),
                )
            )

        if not clauses:
            # Invariant 2: no stamp and no join key means no claim.
            logger.info(
                f"Order {context.order_id} carries no impression stamp and has "
                f"no session or customer - attributing nothing"
            )
            return []

        stmt = select(OfferImpression).where(
            and_(
                OfferImpression.shop_id == context.shop_id,
                # Invariant 1: a held-out shopper saw no offer.
                OfferImpression.is_control.is_(False),
                or_(*clauses),
            )
        )

        if self.session:
            rows = list((await self.session.execute(stmt)).scalars().all())
        else:
            async with get_session_context() as session:
                rows = list((await session.execute(stmt)).scalars().all())

        # Close the loop for stamped impressions: nothing called back for them,
        # so without this they stay 'shown' forever and the learning signal and
        # merchant dashboard both under-report what actually converted.
        await self._mark_accepted_from_stamps(rows, stamped)
        return rows

    async def _mark_accepted_from_stamps(
        self, impressions: List[OfferImpression], stamped: Dict[str, Dict[str, Any]]
    ) -> None:
        """Record the outcome for impressions evidenced by an order line."""
        # Repair revenue as well as outcome.
        #
        # This used to skip anything already marked accepted, on the assumption
        # that an accepted impression already had its revenue. It does not: an
        # extension can report acceptance without an amount — phoenix's
        # reportAccepted is fire-and-forget and its revenue is a client-side
        # estimate that may not arrive — leaving outcome='accepted' with
        # revenue_added NULL. The breakdown then valued the offer at zero and
        # attributed nothing, so a real sale from a real recommendation was
        # silently worth nothing.
        #
        # The order line is the better source anyway: it is what the shopper
        # actually paid, after discounts, rather than a price the browser had.
        pending = [
            imp
            for imp in impressions
            if str(imp.id) in stamped
            and (imp.outcome != "accepted" or imp.revenue_added is None)
        ]
        if not pending:
            return

        for imp in pending:
            line = stamped[str(imp.id)]
            revenue = Decimal(str(line.get("price") or 0)) * Decimal(
                str(line.get("quantity") or 1)
            )
            imp.outcome = "accepted"
            imp.outcome_at = now_utc()
            if imp.revenue_added is None:
                imp.revenue_added = revenue

        logger.info(
            f"Marked {len(pending)} stamped impressions accepted from order lines"
        )

    # ---------- breakdown ----------

    def _build_breakdown(
        self, context: AttributionContext, impressions: List[OfferImpression]
    ) -> List[AttributionBreakdown]:
        """One breakdown row per accepted offer, clamped to the order total.

        The clamp is a money guard, not cosmetic: duplicate outcome callbacks or
        a mis-reported `revenue_added` must never let attributed revenue exceed
        what the shopper actually paid.
        """
        breakdown: List[AttributionBreakdown] = []
        remaining = Decimal(context.purchase_amount or 0)

        for imp in self._strongest_per_offer(impressions):
            extension = _SURFACE_TO_EXTENSION.get((imp.surface or "").lower())
            if extension is None:
                logger.warning(
                    f"Unknown surface {imp.surface!r} on impression {imp.id} - "
                    f"not attributing it"
                )
                continue

            amount = self._revenue_for_impression(imp, context)
            if amount <= 0:
                continue

            if amount > remaining:
                logger.warning(
                    f"Attribution for order {context.order_id} would exceed the "
                    f"order total; clamping {amount} to {remaining}"
                )
                amount = remaining
            if amount <= 0:
                break
            remaining -= amount

            breakdown.append(
                AttributionBreakdown(
                    extension_type=extension,
                    product_id=imp.offer_id,
                    attributed_amount=amount,
                    # An accepted offer earns full credit for the item it added.
                    # There is no journey to split across.
                    attribution_weight=1.0,
                    attribution_type=AttributionType.DIRECT_CLICK,
                    interaction_id=str(imp.id),
                    metadata={
                        "surface": imp.surface,
                        "offer_type": imp.offer_type,
                        "variant_id": imp.variant_id,
                        "impression_group_id": imp.impression_group_id,
                    },
                )
            )

        return breakdown

    # Evidence strength, strongest first. A stamp is deterministic; an accepted
    # callback was observed in the moment; a click is only correlated.
    _EVIDENCE_RANK = {"stamped": 0, "accepted": 1, "clicked": 2}

    def _strongest_per_offer(
        self, impressions: List[OfferImpression]
    ) -> List[OfferImpression]:
        """One impression per recommended product, keeping the best evidence.

        The same product can be recommended more than once to the same shopper
        — seen on two different product pages, say — producing several
        impressions that all point at it. If that product is then bought once,
        crediting every one of those impressions would attribute a single order
        line several times over.

        The order total clamp in `_build_breakdown` would cap the damage, but
        the per-offer breakdown would still be wrong, and that breakdown is
        what a merchant sees when they ask what they are paying for.
        """
        best: Dict[str, OfferImpression] = {}
        for imp in impressions:
            offer = str(imp.offer_id or "")
            if not offer:
                continue
            rank = self._EVIDENCE_RANK.get(imp.outcome or "", 9)
            current = best.get(offer)
            if current is None:
                best[offer] = imp
                continue
            if rank < self._EVIDENCE_RANK.get(current.outcome or "", 9):
                best[offer] = imp
            elif (imp.revenue_added or 0) > (current.revenue_added or 0):
                # Same evidence quality: prefer the one carrying a real figure.
                best[offer] = imp
        return list(best.values())

    def _revenue_for_impression(
        self, imp: OfferImpression, context: AttributionContext
    ) -> Decimal:
        """What the accepted offer added.

        `revenue_added` is reported by the extension at accept time and is the
        preferred figure. Falling back to the order's own line items covers the
        case where the outcome callback landed without an amount.
        """
        if imp.revenue_added is not None:
            revenue = Decimal(str(imp.revenue_added))
            if revenue > 0:
                return revenue

        for product in context.purchase_products or []:
            pid = str(product.get("product_id") or product.get("id") or "")
            vid = str(product.get("variant_id") or "")
            if (imp.offer_id and pid == str(imp.offer_id)) or (
                imp.variant_id and vid == str(imp.variant_id)
            ):
                price = product.get("price") or product.get("total") or 0
                qty = product.get("quantity") or 1
                return Decimal(str(price)) * Decimal(str(qty))

        return Decimal("0.00")

    # ---------- billing guards (preserved) ----------

    async def _is_payment_failed(self, context: AttributionContext) -> bool:
        """Whether the order's money never actually landed."""
        try:
            financial_status = getattr(context, "financial_status", None)
            if financial_status and financial_status in ("VOIDED", "CANCELLED"):
                logger.info(
                    f"💳 Payment failed for order {context.order_id}: {financial_status}"
                )
                return True

            metadata = getattr(context, "metadata", {}) or {}
            if metadata.get("payment_status") in ("failed", "declined", "cancelled"):
                logger.info(
                    f"💳 Payment failed for order {context.order_id}: "
                    f"{metadata.get('payment_status')}"
                )
                return True

            error_message = metadata.get("error_message", "")
            if isinstance(error_message, str) and any(
                kw in error_message.lower()
                for kw in ("declined", "failed", "insufficient", "expired")
            ):
                logger.info(
                    f"💳 Payment failed for order {context.order_id}: {error_message}"
                )
                return True

            return False
        except Exception as e:
            logger.error(
                f"Error checking payment status for order {context.order_id}: {e}"
            )
            return False

    async def _is_subscription_cancelled(self, context: AttributionContext) -> bool:
        """Whether a subscription order was cancelled."""
        try:
            metadata = getattr(context, "metadata", {}) or {}

            status = metadata.get("subscription_status")
            if isinstance(status, str) and status in (
                "cancelled",
                "terminated",
                "expired",
            ):
                logger.info(
                    f"📋 Subscription cancelled for order {context.order_id}: {status}"
                )
                return True

            if metadata.get("cancelled_at") or metadata.get("subscription_cancelled"):
                logger.info(f"📋 Subscription cancelled for order {context.order_id}")
                return True

            return False
        except Exception as e:
            logger.error(
                f"Error checking subscription cancellation for order "
                f"{context.order_id}: {e}"
            )
            return False

    # ---------- result builders ----------

    def _create_empty_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """No accepted offers belong to this order."""
        return AttributionResult(
            order_id=context.order_id,
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=self._link_session_id(context),
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.CALCULATED,
            calculated_at=now_utc(),
            metadata={"reason": "no_accepted_impressions"},
        )

    def _create_rejected_attribution(
        self, context: AttributionContext, scenario: str, reason: str
    ) -> AttributionResult:
        """Attribution deliberately withheld (failed payment, cancellation)."""
        return AttributionResult(
            order_id=context.order_id,
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=self._link_session_id(context),
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.REJECTED,
            calculated_at=now_utc(),
            metadata={"scenario": scenario, "reason": reason},
        )

    # ---------- persistence (preserved) ----------

    async def _store_attribution_result(
        self, result: AttributionResult
    ) -> Optional[str]:
        """Store attribution result in database."""
        try:
            contributing_extensions = [
                {
                    "extension_type": b.extension_type.value,
                    "product_id": b.product_id,
                    "attributed_amount": float(b.attributed_amount),
                    "attribution_weight": b.attribution_weight,
                }
                for b in result.attribution_breakdown
            ]
            attribution_weights = {
                b.extension_type.value: b.attribution_weight
                for b in result.attribution_breakdown
            }
            attributed_revenue = {
                b.extension_type.value: float(b.attributed_amount)
                for b in result.attribution_breakdown
            }
            interactions_by_extension = {
                b.extension_type.value: 1 for b in result.attribution_breakdown
            }

            if self.session:
                return await self._save_attribution(
                    self.session,
                    result,
                    contributing_extensions,
                    attribution_weights,
                    attributed_revenue,
                    interactions_by_extension,
                )
            async with get_session_context() as session:
                return await self._save_attribution(
                    session,
                    result,
                    contributing_extensions,
                    attribution_weights,
                    attributed_revenue,
                    interactions_by_extension,
                )
        except Exception as e:
            if "Unique constraint failed" in str(e) or "duplicate key" in str(e):
                logger.info(
                    f"Attribution for order {result.order_id} already stored "
                    f"concurrently - ignoring"
                )
                return None
            logger.error(
                f"Failed to store attribution for order {result.order_id}: {e}",
                exc_info=True,
            )
            return None

    async def _save_attribution(
        self,
        session: AsyncSession,
        result: AttributionResult,
        contributing_extensions: List[Dict],
        attribution_weights: Dict,
        attributed_revenue: Dict,
        interactions_by_extension: Dict,
    ) -> Optional[str]:
        """Insert or update the purchase_attributions row for this order."""
        stmt = select(PurchaseAttribution).where(
            and_(
                PurchaseAttribution.shop_id == result.shop_id,
                PurchaseAttribution.order_id == str(result.order_id),
            )
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            logger.info(
                f"🔄 Updating existing attribution for order {result.order_id}"
            )
            existing.contributing_extensions = contributing_extensions
            existing.attribution_weights = attribution_weights
            existing.total_revenue = float(result.total_attributed_revenue)
            existing.attributed_revenue = attributed_revenue
            existing.total_interactions = len(result.attribution_breakdown)
            existing.interactions_by_extension = interactions_by_extension
            existing.purchase_at = result.calculated_at
            existing.attribution_algorithm = result.attribution_type.value
            existing.attribution_metadata = result.metadata
            await session.commit()
            return str(existing.id)

        attribution = PurchaseAttribution(
            session_id=result.session_id,
            order_id=str(result.order_id),
            customer_id=result.customer_id,
            shop_id=result.shop_id,
            contributing_extensions=contributing_extensions,
            attribution_weights=attribution_weights,
            total_revenue=float(result.total_attributed_revenue),
            attributed_revenue=attributed_revenue,
            total_interactions=len(result.attribution_breakdown),
            interactions_by_extension=interactions_by_extension,
            purchase_at=result.calculated_at,
            attribution_algorithm=result.attribution_type.value,
            attribution_metadata=result.metadata,
        )
        session.add(attribution)
        await session.commit()
        return str(attribution.id)
