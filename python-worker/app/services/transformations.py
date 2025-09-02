"""
Feature transformation service: computes UserFeatures, ProductFeatures, InteractionFeatures.

Strategy:
- SQL-first aggregations on normalized tables (OrderData, ProductData, CustomerData)
- Upserts with incremental filters using lastComputedAt and fallback window
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from app.core.config import settings
from app.core.database import get_database
from app.core.logging import get_logger, log_error, log_performance

logger = get_logger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _compute_user_features(shop_id: str) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    # Recency (days), total purchases, total spent
    await db.execute_raw(
        """
        INSERT INTO "UserFeatures" ("shopId", "customerId", "totalPurchases", "recencyDays", "avgPurchaseIntervalDays", "totalSpent", "preferredCategory", "lastComputedAt")
        SELECT
          o."shopId",
          o."customerId",
          COUNT(*)::int as total_purchases,
          COALESCE((DATE_PART('day', NOW() - MAX(o."orderDate"))), NULL)::int as recency_days,
          NULL::double precision as avg_interval,
          COALESCE(SUM(o."totalAmount"),0)::double precision as total_spent,
          NULL::text as preferred_category,
          NOW() as last_computed_at
        FROM "OrderData" o
        WHERE o."shopId" = $1 AND o."customerId" IS NOT NULL
        GROUP BY o."shopId", o."customerId"
        ON CONFLICT ("shopId", "customerId") DO UPDATE SET
          "totalPurchases" = EXCLUDED."totalPurchases",
          "recencyDays" = EXCLUDED."recencyDays",
          "totalSpent" = EXCLUDED."totalSpent",
          "lastComputedAt" = NOW();
        """,
        shop_id,
    )

    # Average purchase interval per customer (days)
    await db.execute_raw(
        """
        WITH ordered AS (
          SELECT "shopId","customerId","orderDate",
                 LAG("orderDate") OVER (PARTITION BY "shopId","customerId" ORDER BY "orderDate") AS prev_date
          FROM "OrderData"
          WHERE "shopId" = $1 AND "customerId" IS NOT NULL
        ), diffs AS (
          SELECT "shopId","customerId",
                 EXTRACT(EPOCH FROM ("orderDate" - prev_date))/86400.0 AS diff_days
          FROM ordered WHERE prev_date IS NOT NULL
        )
        UPDATE "UserFeatures" uf
        SET "avgPurchaseIntervalDays" = sub.avg_diff,
            "lastComputedAt" = NOW()
        FROM (
          SELECT "shopId","customerId", AVG(diff_days) AS avg_diff
          FROM diffs
          GROUP BY "shopId","customerId"
        ) sub
        WHERE uf."shopId" = sub."shopId" AND uf."customerId" = sub."customerId";
        """,
        shop_id,
    )

    # Preferred category by highest spend
    await db.execute_raw(
        """
        WITH li AS (
          SELECT o."shopId", o."customerId",
                 jsonb_array_elements(COALESCE(o."lineItems", '[]')) AS li
          FROM "OrderData" o
          WHERE o."shopId" = $1 AND o."customerId" IS NOT NULL
        ), prod_map AS (
          SELECT p."shopId", p."productId", p."category"
          FROM "ProductData" p
          WHERE p."shopId" = $1
        ), joined AS (
          SELECT li."shopId", li."customerId",
                 (li.li->'productId')::text AS product_raw,
                 (li.li->>'quantity')::int AS qty,
                 (li.li->'price'->>'price')::numeric AS unit_price
          FROM li
        ), clean AS (
          SELECT j."shopId", j."customerId",
                 REPLACE(REPLACE(j.product_raw, '"', ''), 'gid://shopify/Product/', '') AS product_id,
                 j.qty, j.unit_price
          FROM joined j
        ), with_cat AS (
          SELECT c."shopId", c."customerId", COALESCE(pm."category", 'unknown') AS category,
                 SUM(COALESCE(c.unit_price,0) * COALESCE(c.qty,1)) AS spend
          FROM clean c
          LEFT JOIN prod_map pm ON pm."shopId" = c."shopId" AND pm."productId" = c.product_id
          GROUP BY c."shopId", c."customerId", COALESCE(pm."category", 'unknown')
        ), ranked AS (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY "shopId","customerId" ORDER BY spend DESC) AS rn
          FROM with_cat
        )
        UPDATE "UserFeatures" uf
        SET "preferredCategory" = r.category,
            "lastComputedAt" = NOW()
        FROM ranked r
        WHERE r.rn = 1 AND uf."shopId" = r."shopId" AND uf."customerId" = r."customerId";
        """,
        shop_id,
    )

    dur = (asyncio.get_event_loop().time() - start) * 1000
    log_performance("compute_user_features", dur, shop_id=shop_id)
    return {"user_features_ms": dur}


async def _compute_product_features(shop_id: str) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    # Popularity from line items
    await db.execute_raw(
        """
        WITH li AS (
          SELECT o."shopId", jsonb_array_elements(COALESCE(o."lineItems", '[]')) AS li
          FROM "OrderData" o WHERE o."shopId" = $1
        ), clean AS (
          SELECT l."shopId",
                 REPLACE(REPLACE((li->'productId')::text, '"', ''), 'gid://shopify/Product/', '') AS product_id,
                 (li->>'quantity')::int AS qty
          FROM li l
        ), agg AS (
          SELECT "shopId", product_id, COALESCE(SUM(qty),0)::int AS pop
          FROM clean
          GROUP BY "shopId", product_id
        )
        INSERT INTO "ProductFeatures" ("shopId", "productId", "popularity", "avgRating", "priceTier", "category", "tags", "lastComputedAt")
        SELECT p."shopId", p.product_id, a.pop, NULL, NULL, pd."category", pd."tags", NOW()
        FROM agg a
        JOIN (
          SELECT DISTINCT "shopId", product_id FROM agg
        ) p ON p."shopId" = a."shopId" AND p.product_id = a.product_id
        LEFT JOIN "ProductData" pd ON pd."shopId" = p."shopId" AND pd."productId" = p.product_id
        ON CONFLICT ("shopId", "productId") DO UPDATE SET
          "popularity" = EXCLUDED."popularity",
          "category" = EXCLUDED."category",
          "tags" = EXCLUDED."tags",
          "lastComputedAt" = NOW();
        """,
        shop_id,
    )

    # Price tier assignment using thresholds
    await db.execute_raw(
        """
        UPDATE "ProductFeatures" pf
        SET "priceTier" = CASE
            WHEN pd."price" < $2 THEN 'low'
            WHEN pd."price" >= $3 THEN 'high'
            ELSE 'mid'
          END,
          "lastComputedAt" = NOW()
        FROM "ProductData" pd
        WHERE pf."shopId" = $1 AND pd."shopId" = pf."shopId" AND pd."productId" = pf."productId";
        """,
        shop_id,
        settings.PRICE_TIER_LOW_MAX,
        settings.PRICE_TIER_HIGH_MIN,
    )

    dur = (asyncio.get_event_loop().time() - start) * 1000
    log_performance("compute_product_features", dur, shop_id=shop_id)
    return {"product_features_ms": dur}


async def _compute_interaction_features(shop_id: str) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    # Purchase counts and last purchase date
    await db.execute_raw(
        """
        WITH li AS (
          SELECT o."shopId", o."customerId", o."orderDate",
                 jsonb_array_elements(COALESCE(o."lineItems", '[]')) AS li
          FROM "OrderData" o
          WHERE o."shopId" = $1 AND o."customerId" IS NOT NULL
        ), clean AS (
          SELECT l."shopId", l."customerId", l."orderDate",
                 REPLACE(REPLACE((li->'productId')::text, '"', ''), 'gid://shopify/Product/', '') AS product_id,
                 (li->>'quantity')::int AS qty
          FROM li l
        ), agg AS (
          SELECT "shopId", "customerId", product_id,
                 COUNT(*)::int AS purchase_count,
                 MAX("orderDate") AS last_purchase
          FROM clean
          GROUP BY "shopId", "customerId", product_id
        )
        INSERT INTO "InteractionFeatures" ("shopId", "customerId", "productId", "purchaseCount", "lastPurchaseDate", "timeDecayedWeight", "lastComputedAt")
        SELECT a."shopId", a."customerId", a.product_id, a.purchase_count, a.last_purchase, NULL, NOW()
        FROM agg a
        ON CONFLICT ("shopId", "customerId", "productId") DO UPDATE SET
          "purchaseCount" = EXCLUDED."purchaseCount",
          "lastPurchaseDate" = EXCLUDED."lastPurchaseDate",
          "lastComputedAt" = NOW();
        """,
        shop_id,
    )

    # Time-decayed weight: sum(exp(-lambda * age_days)) across purchases
    await db.execute_raw(
        """
        WITH li AS (
          SELECT o."shopId", o."customerId", o."orderDate",
                 jsonb_array_elements(COALESCE(o."lineItems", '[]')) AS li
          FROM "OrderData" o
          WHERE o."shopId" = $1 AND o."customerId" IS NOT NULL
        ), clean AS (
          SELECT l."shopId", l."customerId", l."orderDate",
                 REPLACE(REPLACE((li->'productId')::text, '"', ''), 'gid://shopify/Product/', '') AS product_id
          FROM li l
        ), weights AS (
          SELECT "shopId", "customerId", product_id,
                 SUM(EXP(-$2 * GREATEST(0, DATE_PART('day', NOW() - "orderDate")))) AS w
          FROM clean
          GROUP BY "shopId", "customerId", product_id
        )
        UPDATE "InteractionFeatures" i
        SET "timeDecayedWeight" = w.w,
            "lastComputedAt" = NOW()
        FROM weights w
        WHERE i."shopId" = w."shopId" AND i."customerId" = w."customerId" AND i."productId" = w.product_id;
        """,
        shop_id,
        settings.TIME_DECAY_LAMBDA,
    )

    dur = (asyncio.get_event_loop().time() - start) * 1000
    log_performance("compute_interaction_features", dur, shop_id=shop_id)
    return {"interaction_features_ms": dur}


async def run_transformations_for_shop(
    shop_id: str, backfill_if_needed: bool = True
) -> Dict[str, Any]:
    """Run all feature transformations for a shop; return timing stats."""
    stats: Dict[str, Any] = {}
    try:
        u = await _compute_user_features(shop_id)
        p = await _compute_product_features(shop_id)
        i = await _compute_interaction_features(shop_id)
        stats.update(u)
        stats.update(p)
        stats.update(i)
        return stats
    except Exception as e:
        log_error(e, {"operation": "run_transformations_for_shop", "shop_id": shop_id})
        raise
