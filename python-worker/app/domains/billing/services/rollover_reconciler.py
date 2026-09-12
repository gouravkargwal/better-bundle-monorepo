"""
Rollover reconciliation sweep for shops suspended due to usage caps.

Why this has to exist
---------------------
Shopify App Usage Pricing operates on a 30-day billing interval. When a new
30-day interval begins, Shopify resets `balanceUsed` to 0. However, Shopify does
NOT emit any webhook for natural cycle rollovers (it only emits
APP_SUBSCRIPTIONS_UPDATE when a merchant manually edits a cap or cancels).

When a merchant exceeds their capped amount, our app suspends them locally to
prevent unpaid recommendations. Without this reconciler, the shop remains
permanently suspended even though Shopify has granted a fresh spending cap.

How the sweep works
-------------------
1. Query `shop_subscriptions` where `status == SUSPENDED` and `is_active = True`.
2. For each, call Shopify's GraphQL API (`get_subscription_status`) using the
   existing `ShopifyUsageBillingServiceV2` to inspect live `cappedAmount` and
   `balanceUsed`.
3. Rollover Test:
   - If `suspended_balance_used` is recorded: `live_balance_used < suspended_balance_used`.
     A drop in balance is the only unambiguous indicator of a cycle rollover.
   - For legacy rows without `suspended_balance_used`: if `cappedAmount - live_balance_used >= 1.00`,
     reactivate; otherwise record `suspended_balance_used` for subsequent passes.
4. On rollover:
   - Set subscription `status = ACTIVE` and shop `is_active = True`.
   - Clear `suspended_balance_used` and invalidate suspension cache.
   - Record an immutable row in `suspension_audit_log` (`REACTIVATED`).
   - Drain backlog: republish Kafka `record_usage` events for all pending
     commissions for that shop.
"""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_

from app.core.config.kafka_settings import kafka_settings
from app.core.database.models import (
    Shop,
    ShopSubscription,
    SubscriptionStatus,
    SuspensionAuditLog,
)
from app.core.database.session import get_transaction_context
from app.core.messaging.event_publisher import EventPublisher
from app.core.single_run import claim
from app.domains.billing.repositories.billing_repository_v2 import BillingRepositoryV2
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
from app.domains.billing.services.shopify_usage_billing_service_v2 import (
    ShopifyUsageBillingServiceV2,
)
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)

# Bounded batch so large backlogs don't overwhelm external API limits
MAX_SUSPENDED_SHOPS_PER_SWEEP = 50

# Fallback capacity threshold for legacy suspensions lacking suspended_balance_used
SMALLEST_PLAUSIBLE_COMMISSION = Decimal("1.00")

# Interval between sweeps (1 hour)
RECONCILE_INTERVAL_SECONDS = 3600


async def drain_pending_commissions(shop_id: str, limit: int = 100) -> int:
    """Drain unbilled / overflow commissions for a reactivated shop via Kafka."""
    async with get_transaction_context() as session:
        commission_service = CommissionServiceV2(session)
        pending = await commission_service.get_pending_commissions(
            shop_id=shop_id, limit=limit
        )
        comm_ids = [comm.id for comm in pending]

    if not comm_ids:
        return 0

    # Publish Kafka events completely outside any open database transaction
    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()
    published = 0
    try:
        for comm_id in comm_ids:
            try:
                await publisher.publish_shopify_usage_event(
                    {
                        "event_type": "record_usage",
                        "shop_id": shop_id,
                        "commission_id": comm_id,
                        "trigger": "rollover_drain",
                    }
                )
                published += 1
            except Exception as e:
                logger.error(
                    f"Failed to publish usage drain for commission {comm_id}: {e}"
                )
    finally:
        await publisher.close()

    logger.info(
        f"📤 Rollover drain republished {published}/{len(comm_ids)} usage events for shop {shop_id}"
    )
    return published


async def reconcile_rollovers_once(
    limit: int = MAX_SUSPENDED_SHOPS_PER_SWEEP,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute one reconciliation pass across suspended shops."""
    # 1. Fetch candidate suspended shops in a short, bounded read transaction
    async with get_transaction_context() as session:
        query = (
            select(ShopSubscription, Shop)
            .join(Shop, Shop.id == ShopSubscription.shop_id)
            .where(
                and_(
                    ShopSubscription.status == SubscriptionStatus.SUSPENDED,
                    ShopSubscription.is_active.is_(True),
                    ShopSubscription.shopify_subscription_id.is_not(None),
                )
            )
            .limit(limit)
        )
        result = await session.execute(query)
        candidates = [
            (
                sub.id,
                sub.shopify_subscription_id,
                dict(sub.shop_subscription_metadata or {}),
                shop.id,
                shop.shop_domain,
                shop.access_token,
            )
            for sub, shop in result.all()
        ]

    if not candidates:
        return {
            "checked": 0,
            "reactivated": 0,
            "drained_commissions": 0,
            "dry_run": dry_run,
        }

    logger.info(f"🔍 Rollover reconciler checking {len(candidates)} suspended shops")

    reactivated_count = 0
    total_drained = 0

    # 2. Query Shopify GraphQL for each shop completely outside DB transaction context
    # This prevents holding DB connection pool resources during remote HTTP requests
    usage_service = ShopifyUsageBillingServiceV2(session=None, billing_repository=None)

    for (
        sub_id,
        shopify_subscription_id,
        metadata,
        shop_id,
        shop_domain,
        access_token,
    ) in candidates:
        if not access_token or not shop_domain:
            logger.warning(
                f"⚠️ Shop {shop_id} missing access token or domain; skipping rollover check"
            )
            continue

        try:
            status_data = await usage_service.get_subscription_status(
                shop_domain=shop_domain,
                access_token=access_token,
                subscription_id=shopify_subscription_id,
            )

            if not status_data:
                logger.warning(
                    f"⚠️ Could not fetch subscription status for shop {shop_id} ({shopify_subscription_id})"
                )
                continue

            line_items = status_data.get("lineItems", [])
            pricing = (
                line_items[0].get("plan", {}).get("pricingDetails", {})
                if line_items
                else {}
            )

            if pricing.get("__typename") != "AppUsagePricing":
                logger.warning(
                    f"⚠️ Subscription {shopify_subscription_id} for shop {shop_id} is not AppUsagePricing"
                )
                continue

            capped_amount = Decimal(
                str(pricing.get("cappedAmount", {}).get("amount", "0"))
            )
            balance_used = Decimal(
                str(pricing.get("balanceUsed", {}).get("amount", "0"))
            )

            suspended_balance_raw = metadata.get("suspended_balance_used")

            is_rolled_over = False
            if suspended_balance_raw is not None:
                suspended_balance = Decimal(str(suspended_balance_raw))
                # Strict rollover test: balance must have dropped
                if balance_used < suspended_balance:
                    is_rolled_over = True
                    logger.info(
                        f"🎉 Rollover confirmed for shop {shop_id}: "
                        f"balance dropped from ${suspended_balance} to ${balance_used} (cap: ${capped_amount})"
                    )
            else:
                # Legacy suspension (no baseline recorded):
                # A true 30-day reset resets balance_used to 0.00.
                if balance_used == Decimal("0.00"):
                    is_rolled_over = True
                    logger.info(
                        f"🎉 Legacy rollover detected for shop {shop_id}: "
                        f"balance reset to $0.00 (cap: ${capped_amount})"
                    )
                else:
                    # Shop was capped mid-cycle before we started recording suspended_balance_used.
                    # Record baseline balance so next sweep can apply the strict drop test
                    async with get_transaction_context() as update_session:
                        sub = await update_session.get(ShopSubscription, sub_id)
                        if sub:
                            sub_metadata = dict(sub.shop_subscription_metadata or {})
                            sub_metadata["suspended_balance_used"] = float(balance_used)
                            sub_metadata["suspended_at"] = now_utc().isoformat()
                            sub.shop_subscription_metadata = sub_metadata
                            await update_session.commit()
                    logger.info(
                        f"Recorded baseline balance ${balance_used} for legacy suspended shop {shop_id} "
                        f"to prevent premature reactivation"
                    )

            if not is_rolled_over:
                continue

            if dry_run:
                reactivated_count += 1
                continue

            # 3. Reactivate in a short DB transaction
            async with get_transaction_context() as reactivate_session:
                sub = await reactivate_session.get(ShopSubscription, sub_id)
                shop_record = await reactivate_session.get(Shop, shop_id)
                if not sub or not shop_record:
                    continue

                sub_metadata = dict(sub.shop_subscription_metadata or {})
                sub_metadata.pop("suspended_balance_used", None)
                sub_metadata["reactivated_at"] = now_utc().isoformat()
                sub.status = SubscriptionStatus.ACTIVE
                sub.shop_subscription_metadata = sub_metadata
                sub.updated_at = now_utc()

                shop_record.is_active = True
                shop_record.suspended_at = None
                shop_record.suspension_reason = None
                shop_record.updated_at = now_utc()

                audit_log = SuspensionAuditLog(
                    shop_id=shop_id,
                    action="REACTIVATED",
                    reason=(
                        f"Shopify 30-day billing cycle rollover detected "
                        f"(balance: ${balance_used}, cap: ${capped_amount})"
                    ),
                    triggered_by="system",
                    metadata_json=json.dumps(
                        {
                            "capped_amount": float(capped_amount),
                            "balance_used": float(balance_used),
                            "previous_suspended_balance": (
                                float(suspended_balance_raw)
                                if suspended_balance_raw is not None
                                else None
                            ),
                        }
                    ),
                )
                reactivate_session.add(audit_log)
                await reactivate_session.commit()

            # Invalidate suspension Redis cache
            try:
                from app.core.redis_client import get_redis_client

                redis = await get_redis_client()
                await redis.delete(f"suspension:{shop_id}")
            except Exception as cache_err:
                logger.debug(
                    f"Could not invalidate Redis suspension cache for {shop_id}: {cache_err}"
                )

            reactivated_count += 1

            # Drain pending commissions
            drained = await drain_pending_commissions(shop_id)
            total_drained += drained

        except Exception as e:
            logger.error(
                f"❌ Error checking rollover for shop {shop_id}: {e}", exc_info=True
            )

    logger.info(
        f"✅ Rollover reconciliation completed: {reactivated_count} reactivated, "
        f"{total_drained} commissions drained"
    )
    return {
        "checked": len(candidates),
        "reactivated": reactivated_count,
        "drained_commissions": total_drained,
        "dry_run": dry_run,
    }

    logger.info(
        f"✅ Rollover reconciliation completed: {reactivated_count} reactivated, "
        f"{total_drained} commissions drained"
    )
    return {
        "checked": len(rows),
        "reactivated": reactivated_count,
        "drained_commissions": total_drained,
        "dry_run": dry_run,
    }


async def run_forever(interval: int = RECONCILE_INTERVAL_SECONDS) -> None:
    """Run rollover reconciliation loop forever."""
    logger.info(f"🔄 Rollover reconciler started (every {interval}s)")
    while True:
        try:
            await asyncio.sleep(interval)
            async with claim("rollover_reconciler") as mine:
                if mine:
                    result = await reconcile_rollovers_once()
                    if result.get("reactivated", 0) > 0:
                        logger.info(f"Rollover reconciler pass: {result}")
        except asyncio.CancelledError:
            logger.info("Rollover reconciler stopped")
            raise
        except Exception as e:
            logger.error(f"Rollover reconciler loop error: {e}", exc_info=True)
