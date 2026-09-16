"""
Reconcile local product/collection/customer data against Shopify's live catalog.

Why this exists
---------------
Shopify webhook delivery is not guaranteed (their own documentation says so).
The ingestion backstop covers orders; this covers the other three entity types.
Without it, a product deleted from Shopify but never notified via webhook stays
``is_active = true`` in our database and continues appearing in recommendations.

How it works
------------
Each sweep compares Shopify's live entity count against our local active count.
If they match, the shop is clean for that entity type — no work needed. If they
differ, we fetch the full set of Shopify IDs and deactivates anything we still
hold that Shopify no longer has.

The count check is a single cheap GraphQL query per entity type. The full ID
diff is more expensive (paginated) but happens rarely — only when the counts
diverge, which means a deletion (or creation) actually occurred.

Design follows the ingestion backstop: stateless, bounded, advisory-locked.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Type

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import select, text

from app.core.database.models.shop import Shop
from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.core.metrics import (
    reconciler_duration,
    reconciler_runs_total,
)
from app.core.single_run import claim

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------
RECONCILER_INTERVAL_SECONDS = 3600  # 1 hour — catalog changes rarely
MAX_SHOPS_PER_SWEEP = 25
# Bound total GraphQL calls so one large catalog cannot starve the cycle.
# A 10k-product catalog needs ~40 pages; this leaves headroom for 2-3 shops
# that actually differ.
MAX_API_CALLS_PER_CYCLE = 150


# ---------------------------------------------------------------------------
# Entity configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntityConfig:
    model: Type  # SQLAlchemy model class
    id_field: str  # column name on the model (e.g. "product_id")
    table_name: str  # for SQL text queries
    # GraphQL query that returns IDs.  Uses $first/$after pagination.
    # The query MUST alias the connection as `entity_connection`.
    id_query: str
    # Optional: a lightweight count query.  If None, always do full diff.
    count_query: str | None = None


PRODUCTS_CONFIG = EntityConfig(
    model=None,  # resolved at runtime to avoid circular imports
    id_field="product_id",
    table_name="product_data",
    count_query="query { productsCount { count } }",
    id_query="""
    query($first: Int!, $after: String) {
        products(first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges { node { id } }
        }
    }
    """,
)

COLLECTIONS_CONFIG = EntityConfig(
    model=None,
    id_field="collection_id",
    table_name="collection_data",
    count_query="query { collectionsCount { count } }",
    id_query="""
    query($first: Int!, $after: String) {
        collections(first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges { node { id } }
        }
    }
    """,
)

# Customers have no `customersCount` query in Shopify's GraphQL API, so we
# always do the full ID diff.
CUSTOMERS_CONFIG = EntityConfig(
    model=None,
    id_field="customer_id",
    table_name="customer_data",
    count_query=None,
    id_query="""
    query($first: Int!, $after: String) {
        customers(first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges { node { id } }
        }
    }
    """,
)

ENTITY_CONFIGS: List[EntityConfig] = [PRODUCTS_CONFIG, COLLECTIONS_CONFIG, CUSTOMERS_CONFIG]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


async def _shopify_count(
    client, shop_domain: str, count_query: str
) -> int | None:
    """Fetch a single count from Shopify. Returns None on failure."""
    try:
        result = await client.execute_query(count_query, {}, shop_domain)
        # productsCount, collectionsCount
        for key in ("productsCount", "collectionsCount"):
            if key in result and result[key] is not None:
                return result[key].get("count", 0)
        return 0
    except Exception as e:
        logger.warning(f"Could not fetch Shopify count for {shop_domain}: {e}")
        return None


async def _shopify_ids(
    client, shop_domain: str, id_query: str, max_calls: int
) -> Set[str] | None:
    """Paginate through all IDs from Shopify. Returns None on failure."""
    ids: Set[str] = set()
    cursor = None
    calls = 0

    while calls < max_calls:
        calls += 1
        variables = {"first": 250, "after": cursor}
        try:
            result = await client.execute_query(id_query, variables, shop_domain)
        except Exception as e:
            logger.warning(f"Failed to fetch IDs page for {shop_domain}: {e}")
            return None

        # The connection key varies by query; find it dynamically.
        connection = None
        for key in ("products", "collections", "customers"):
            if key in result:
                connection = result[key]
                break
        if not connection:
            break

        edges = connection.get("edges") or []
        for edge in edges:
            gid = edge.get("node", {}).get("id", "")
            if gid.startswith("gid://"):
                gid = gid.split("/")[-1]
            if gid:
                ids.add(gid)

        page_info = connection.get("pageInfo") or {}
        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        if not has_next:
            break

    return ids


async def _local_active_ids(
    table_name: str, id_field: str, shop_id: str
) -> Set[str]:
    """Active entity IDs we hold locally."""
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                text(
                    f"SELECT {id_field} FROM {table_name} "
                    f"WHERE shop_id = :shop_id AND is_active = true"
                ),
                {"shop_id": shop_id},
            )
        ).all()
    return {str(r[0]) for r in rows}


async def _local_active_count(
    table_name: str, shop_id: str
) -> int:
    async with get_transaction_context() as session:
        return (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {table_name} "
                    f"WHERE shop_id = :shop_id AND is_active = true"
                ),
                {"shop_id": shop_id},
            )
        ).scalar_one()


async def _deactivate_ids(
    table_name: str, id_field: str, shop_id: str, ids: Set[str]
) -> int:
    """Mark entities as inactive. Returns count deactivated."""
    if not ids:
        return 0
    async with get_transaction_context() as session:
        result = await session.execute(
            text(
                f"UPDATE {table_name} "
                f"SET is_active = false, updated_at = NOW() "
                f"WHERE shop_id = :shop_id AND {id_field} = ANY(:ids)"
            ),
            {"shop_id": shop_id, "ids": list(ids)},
        )
        return result.rowcount or 0


# ---------------------------------------------------------------------------
# Per-entity-type sweep
# ---------------------------------------------------------------------------
async def _sweep_entity(
    entity: EntityConfig,
    client,
    shop_domain: str,
    shop_id: str,
    api_budget: int,
) -> Dict[str, Any]:
    """Reconcile one entity type for one shop. Returns stats."""
    local_count = await _local_active_count(entity.table_name, shop_id)

    # Fast path: compare counts.  If they match, nothing changed.
    if entity.count_query and local_count > 0:
        remote_count = await _shopify_count(client, shop_domain, entity.count_query)
        if remote_count is not None and remote_count == local_count:
            return {
                "entity": entity.table_name,
                "local_count": local_count,
                "remote_count": remote_count,
                "deactivated": 0,
                "skipped": "counts_match",
            }

    # Slow path: full ID diff.
    if api_budget <= 0:
        return {
            "entity": entity.table_name,
            "local_count": local_count,
            "remote_count": None,
            "deactivated": 0,
            "skipped": "api_budget_exhausted",
        }

    remote_ids = await _shopify_ids(
        client, shop_domain, entity.id_query, max_calls=api_budget
    )
    if remote_ids is None:
        return {
            "entity": entity.table_name,
            "local_count": local_count,
            "remote_count": None,
            "deactivated": 0,
            "skipped": "fetch_failed",
        }

    local_ids = await _local_active_ids(entity.table_name, entity.id_field, shop_id)
    stale = local_ids - remote_ids

    deactivated = 0
    if stale:
        deactivated = await _deactivate_ids(
            entity.table_name, entity.id_field, shop_id, stale
        )
        logger.warning(
            f"Deactivated {deactivated} {entity.table_name} for {shop_domain} "
            f"(local={local_count}, remote={len(remote_ids)})"
        )

    return {
        "entity": entity.table_name,
        "local_count": local_count,
        "remote_count": len(remote_ids),
        "deactivated": deactivated,
    }


# ---------------------------------------------------------------------------
# Top-level sweep
# ---------------------------------------------------------------------------
async def sweep_once(dry_run: bool = False) -> Dict[str, Any]:
    """One pass across every active shop for all entity types."""
    from app.domains.shopify.services.api.product_client import ProductAPIClient

    start_time = time.perf_counter()
    with tracer.start_as_current_span("reconciler.entity_reconciler.sweep") as span:
        span.set_attribute("dry_run", dry_run)
        try:
            shops = await _active_shops()
            total_deactivated = 0
            total_skipped = 0
            failed: List[str] = []

            async with ProductAPIClient() as client:
                for shop in shops:
                    api_budget = MAX_API_CALLS_PER_CYCLE
                    try:
                        # The client authenticates from a per-domain token map
                        # that starts empty. _active_shops already read the
                        # token; without handing it over every request goes out
                        # with an empty X-Shopify-Access-Token header and comes
                        # back 401, so the sweep could never reconcile anything.
                        await client.set_access_token(
                            shop["shop_domain"], shop["access_token"]
                        )
                        for entity in ENTITY_CONFIGS:
                            if api_budget <= 0:
                                total_skipped += 1
                                continue
                            result = await _sweep_entity(
                                entity,
                                client,
                                shop["shop_domain"],
                                shop["id"],
                                api_budget,
                            )
                            total_deactivated += result.get("deactivated", 0)
                            if result.get("skipped"):
                                total_skipped += 1
                            # Each page costs 1 from the budget.  A count-only
                            # path costs 1 call; a full diff costs N pages.
                            api_budget -= 1
                    except Exception as e:
                        logger.error(
                            f"Entity reconciler failed for {shop['shop_domain']}: {e}",
                            extra={
                                "reconciler": "entity_reconciler",
                                "shop_domain": shop["shop_domain"],
                            },
                        )
                        failed.append(shop["shop_domain"])

            duration = time.perf_counter() - start_time
            span.set_attribute("shops_checked", len(shops) - len(failed))
            span.set_attribute("entities_deactivated", total_deactivated)

            reconciler_runs_total.add(
                1, {"reconciler": "entity_reconciler", "status": "success"}
            )
            reconciler_duration.record(duration, {"reconciler": "entity_reconciler"})

            if total_deactivated > 0:
                logger.warning(
                    f"⚠️ Entity reconciler deactivated {total_deactivated} "
                    f"stale entities across {len(shops)} shop(s)"
                )
            elif not failed:
                logger.info(
                    f"✅ Entity reconciler: {len(shops)} shop(s) checked, "
                    f"nothing stale"
                )

            if failed:
                logger.error(
                    f"🚨 Entity reconciler could not check {len(failed)} of "
                    f"{len(shops)} shop(s): {', '.join(failed)}"
                )

            return {
                "shops": len(shops),
                "checked": len(shops) - len(failed),
                "failed": failed,
                "deactivated": total_deactivated,
                "skipped": total_skipped,
                "duration": duration,
                "dry_run": dry_run,
            }
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(
                1, {"reconciler": "entity_reconciler", "status": "error"}
            )
            reconciler_duration.record(duration, {"reconciler": "entity_reconciler"})
            raise


async def run_forever(interval: int = RECONCILER_INTERVAL_SECONDS) -> None:
    """Sweep on a loop. Started at app startup, cancelled at shutdown."""
    logger.info(f"Entity reconciler started (every {interval}s)")
    while True:
        try:
            async with claim("entity_reconciler") as mine:
                if mine:
                    await sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Entity reconciler sweep failed: {e}", exc_info=True)
        await asyncio.sleep(interval)
