"""Catches orders that webhooks never delivered.

This exists because of an outage that lasted an unknown number of days and that
nothing detected. The app's webhook subscriptions were registered against
`api_version = "2024-07"`, which Shopify had removed, so no webhook was ever
delivered. Orders were placed, paid, and carried our recommendation stamps —
and none of them reached the database. Revenue went unattributed and unbilled,
and the first sign of trouble was a merchant noticing.

The reason nothing caught it is that data had exactly two routes in: the
one-time onboarding backfill, and webhooks. Nothing ever asked Shopify "is
there anything I have not seen?". The attribution reconciler could not help —
it reconciles orders already in `order_data` against their attribution, so with
the ingestion side broken it swept faithfully every 15 minutes and correctly
found nothing.

Shopify's own position is that webhook delivery is not guaranteed and that apps
must reconcile through the API, so this is a requirement rather than a
belt-and-braces extra.

Two jobs in one sweep:

  1. **Recovery.** Anything Shopify has that we do not is republished down the
     normal webhook path, so it is ingested, normalised and attributed exactly
     as if the webhook had arrived.

  2. **Detection.** A non-empty result *is* the alarm. If this sweep is finding
     orders, webhook delivery is broken, and that gets logged at ERROR with the
     count. This is the dead-man's switch, and it comes for free — no separate
     heartbeat to maintain and no way for the alarm itself to silently stop
     working while looking healthy.

Deliberately stateless. A fixed overlapping lookback window rather than a
stored cursor: a cursor is one more piece of state that can stick, skip, or be
corrupted, and when it does the failure is silent — which is the exact failure
mode this file exists to prevent. Re-examining the same 24 hours on every pass
costs one cheap ID-only query per shop and cannot get stuck.
"""

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Set

from sqlalchemy import select, text

from app.core.config.kafka_settings import kafka_settings
from app.core.database.models.shop import Shop
from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.shared.helpers import now_utc

logger = get_logger(__name__)

# How often to sweep. Long enough that it costs nothing, short enough that a
# webhook outage is caught within the hour rather than by a merchant.
BACKSTOP_INTERVAL_SECONDS = 1800  # 30 minutes

# How far back each sweep looks. Comfortably longer than the interval so an
# order placed during a pass cannot fall between two windows, and long enough
# to absorb Shopify's own webhook retry schedule before we conclude it failed.
BACKSTOP_LOOKBACK_HOURS = 24

# Orders inspected per shop per sweep. Bounded so one busy shop cannot starve
# the others, and so a long outage drains over several passes instead of
# flooding the collection consumer at once.
MAX_ORDERS_PER_SHOP = 250

# Shops per sweep, for the same reason.
MAX_SHOPS_PER_SWEEP = 25


async def _active_shops() -> List[Dict[str, str]]:
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                select(Shop.id, Shop.shop_domain, Shop.access_token)
                .where(Shop.is_active.is_(True))
                .limit(MAX_SHOPS_PER_SWEEP)
            )
        ).all()
    return [
        {"id": r.id, "shop_domain": r.shop_domain, "access_token": r.access_token}
        for r in rows
        if r.shop_domain and r.access_token
    ]


async def _local_order_ids(shop_id: str, since) -> Set[str]:
    """Order ids we already hold for this shop inside the window."""
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT order_id FROM order_data
                    WHERE shop_id = :shop_id AND order_date >= :since
                    """
                ),
                {"shop_id": shop_id, "since": since},
            )
        ).all()
    return {str(r.order_id) for r in rows}


async def _shopify_order_ids(shop: Dict[str, str], since) -> Set[str]:
    """Order ids Shopify has for this shop inside the window.

    Uses the same paginated client the collection pipeline uses, with a
    `updated_at:>=` filter. `updated_at` rather than `created_at` on purpose: an
    order edited after the fact — a post-purchase add, a refund — also needs
    re-ingesting, and keying on creation time would miss it.
    """
    from app.domains.shopify.services.api.order_client import OrderAPIClient

    client = OrderAPIClient()
    await client.set_access_token(shop["shop_domain"], shop["access_token"])

    query = f"updated_at:>='{since.strftime('%Y-%m-%dT%H:%M:%SZ')}'"
    result = await client.get_orders(
        shop_domain=shop["shop_domain"],
        limit=MAX_ORDERS_PER_SHOP,
        query=query,
    )

    ids: Set[str] = set()
    for edge in (result or {}).get("edges") or []:
        node = edge.get("node") or {}
        gid = node.get("id") or ""
        # Shopify returns GIDs; order_data stores the numeric id.
        ids.add(gid.split("/")[-1] if gid.startswith("gid://") else str(gid))
    ids.discard("")
    return ids


async def sweep_shop(shop: Dict[str, str], dry_run: bool = False) -> Dict[str, Any]:
    """Compare one shop against Shopify and republish anything missing."""
    since = now_utc() - timedelta(hours=BACKSTOP_LOOKBACK_HOURS)

    remote = await _shopify_order_ids(shop, since)
    if not remote:
        return {"shop_domain": shop["shop_domain"], "missing": 0, "published": 0}

    local = await _local_order_ids(shop["id"], since)
    missing = sorted(remote - local)

    if not missing:
        return {"shop_domain": shop["shop_domain"], "missing": 0, "published": 0}

    # This is the alarm. Orders existing in Shopify but not here means webhook
    # delivery is failing right now — the condition that previously went
    # unnoticed for days.
    logger.error(
        f"🚨 Webhook delivery appears broken for {shop['shop_domain']}: "
        f"{len(missing)} of {len(remote)} orders in the last "
        f"{BACKSTOP_LOOKBACK_HOURS}h are missing locally. Recovering them. "
        f"Check that the app's webhook subscriptions are registered against a "
        f"supported api_version."
    )

    if dry_run:
        return {
            "shop_domain": shop["shop_domain"],
            "missing": len(missing),
            "published": 0,
            "dry_run": True,
        }

    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()
    published = 0
    try:
        for order_id in missing:
            try:
                # Deliberately the same event a webhook produces, so the order
                # flows through collection, normalisation and attribution by the
                # identical path — including the `trigger: "webhook"` marking
                # that makes it attributable at all. `recovered_by` is carried
                # for traceability when someone asks why a charge appeared late.
                await publisher.publish_shopify_event(
                    {
                        "event_type": "order_paid",
                        "shop_id": shop["id"],
                        "shop_domain": shop["shop_domain"],
                        "shopify_id": str(order_id),
                        "recovered_by": "ingestion_backstop",
                    }
                )
                published += 1
            except Exception as e:
                logger.error(
                    f"Failed to republish missing order {order_id} for "
                    f"{shop['shop_domain']}: {e}"
                )
    finally:
        await publisher.close()

    return {
        "shop_domain": shop["shop_domain"],
        "missing": len(missing),
        "published": published,
    }


async def sweep_once(dry_run: bool = False) -> Dict[str, Any]:
    """One pass across every active shop."""
    shops = await _active_shops()
    results = []
    failed = []
    for shop in shops:
        try:
            results.append(await sweep_shop(shop, dry_run=dry_run))
        except Exception as e:
            # One shop's expired token or rate limit must not stop the others,
            # but it must not be mistaken for a clean result either.
            logger.error(f"Ingestion backstop failed for {shop['shop_domain']}: {e}")
            failed.append(shop["shop_domain"])

    total_missing = sum(r.get("missing", 0) for r in results)
    total_published = sum(r.get("published", 0) for r in results)

    # A shop that errored was never actually checked, so it cannot be reported
    # as healthy. This sweep is the only webhook-failure alarm there is; an
    # "everything fine" line covering shops it failed to examine would recreate
    # the exact blind spot the backstop exists to close — and it would look
    # reassuring while doing it.
    if failed:
        logger.error(
            f"🚨 Ingestion backstop could not check {len(failed)} of {len(shops)} "
            f"shop(s): {', '.join(failed)}. Webhook delivery is UNVERIFIED for "
            f"them — this is not a clean result."
        )
    elif total_missing == 0:
        logger.info(
            f"✅ Ingestion backstop: {len(shops)} shop(s) checked, nothing missing"
        )

    return {
        "shops": len(shops),
        "checked": len(results),
        "failed": failed,
        "missing": total_missing,
        "published": total_published,
        "results": results,
        "dry_run": dry_run,
    }


async def run_forever(interval: int = BACKSTOP_INTERVAL_SECONDS) -> None:
    """Sweep on a loop. Started at app startup, cancelled at shutdown."""
    logger.info(f"Ingestion backstop started (every {interval}s)")
    while True:
        try:
            await sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # A dead backstop must not take the app with it, but it must be
            # loud: while it is down, the only webhook-failure alarm is off.
            logger.error(f"Ingestion backstop sweep failed: {e}", exc_info=True)
        await asyncio.sleep(interval)
