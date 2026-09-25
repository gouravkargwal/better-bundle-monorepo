"""
Co-purchase mining: turn a shop's order history into observed edge scores.

Runs on the batch instance, never on the request path. Pair counting is pushed
into Postgres — a self-join over deduplicated baskets — rather than pulled into
Python, so a shop with 50,000 orders costs one query instead of a materialised
basket list.

Writes `observed_count` and `observed_llr` onto `product_edges`, creating edges
that the LLM prior never predicted (real data outranks a guess) and then
re-blending every affected row.
"""

import logging
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database.models.product_edge import ProductEdge
from app.core.database.session import get_transaction_context
from app.shared.helpers import now_utc

from .scoring import (
    BLEND_FULL_OBSERVATIONS,
    BLEND_MIN_OBSERVATIONS,
    observed_score,
)

logger = logging.getLogger(__name__)

# Trailing window for co-purchase mining. Long enough to accumulate evidence,
# short enough that last season's catalog does not drive today's offers.
LOOKBACK_DAYS = 90

# Orders whose money actually landed. Refunded statuses stay in: the refund is
# subtracted at the line-item level below, which is finer than dropping the
# whole order — a shopper who kept two of three items still tells us those two
# go together.
COUNTED_FINANCIAL_STATUSES = ("paid", "partially_refunded", "refunded")

# A 60-line order is a wholesale or trade order, not a shopping basket. Its
# C(60,2) = 1,770 pairs would swamp the genuine signal, so skip it.
MAX_BASKET_SIZE = 20

# Pairs seen once are noise and would bloat the table on every run.
MIN_PAIR_COUNT = 2


# The basket population, written once and shared by all three queries below.
# k11, k12/k21 and the order total have to be counted over exactly the same set
# of orders or the LLR is meaningless, and three hand-maintained copies of this
# predicate would eventually disagree.
#
# Refunds are subtracted per line item rather than by dropping whole orders: a
# shopper who kept two of three items still tells us those two belong together.
# An item is dropped only once the returned quantity covers what was bought.
_BASKETS_CTE = """
    refunded AS (
        SELECT rd.order_id,
               item->>'product_id'               AS product_id,
               SUM((item->>'quantity')::numeric) AS refunded_qty
        FROM refund_data rd,
             LATERAL jsonb_array_elements(rd.refund_line_items::jsonb) AS item
        WHERE rd.shop_id = :shop_id
          AND rd.refund_line_items IS NOT NULL
          AND jsonb_typeof(rd.refund_line_items::jsonb) = 'array'
          AND item->>'product_id' IS NOT NULL
        GROUP BY rd.order_id, item->>'product_id'
    ),
    baskets AS (
        SELECT o.id AS order_id, li.product_id
        FROM order_data o
        JOIN line_item_data li ON li.order_id = o.id
        LEFT JOIN refunded r
               ON r.order_id = o.id AND r.product_id = li.product_id
        WHERE o.shop_id = :shop_id
          AND o.order_date >= :cutoff
          AND o.cancelled_at IS NULL
          AND LOWER(COALESCE(o.financial_status, '')) = ANY(:statuses)
          AND li.product_id IS NOT NULL
        GROUP BY o.id, li.product_id
        HAVING SUM(li.quantity) > COALESCE(MAX(r.refunded_qty), 0)
    )
"""


# Deduplicate to one row per (order, product) so a customer buying three of the
# same item does not inflate the basket, then pair products within each order.
# `p1 < p2` keeps one row per unordered pair; edges are written both ways after.
_PAIR_SQL = text(
    f"""
    WITH {_BASKETS_CTE},
    sized AS (
        SELECT order_id FROM baskets
        GROUP BY order_id
        HAVING COUNT(*) BETWEEN 2 AND :max_basket
    ),
    kept AS (
        SELECT b.order_id, b.product_id
        FROM baskets b JOIN sized s ON s.order_id = b.order_id
    )
    SELECT a.product_id AS product_a,
           b.product_id AS product_b,
           COUNT(*)     AS pair_count
    FROM kept a
    JOIN kept b ON a.order_id = b.order_id AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    HAVING COUNT(*) >= :min_pair
    """
)

# Order counts per product, over the same filtered population, so k12/k21 are
# consistent with k11. Counts every qualifying order, including single-item ones,
# because "A sold alone 400 times" is exactly what makes a pair unsurprising.
_ITEM_SQL = text(
    f"""
    WITH {_BASKETS_CTE}
    SELECT product_id, COUNT(*) AS order_count FROM baskets GROUP BY product_id
    """
)

# Counted over the basket population rather than over `order_data`, so that an
# order left empty by refunds is not still sitting in the denominator making
# every surviving pair look rarer than it is.
_TOTAL_SQL = text(
    f"""
    WITH {_BASKETS_CTE}
    SELECT COUNT(DISTINCT order_id) FROM baskets
    """
)


def contingency(
    pair_count: int, count_a: int, count_b: int, total_orders: int
) -> Tuple[int, int, int, int]:
    """Build the 2x2 table LLR needs from three counts.

    k22 is floored at zero: `total_orders` is counted over the same population
    as the item counts, but a mismatch (a concurrent sync, say) must degrade the
    score rather than feed a negative count into the entropy calculation.
    """
    k11 = pair_count
    k12 = max(0, count_a - pair_count)
    k21 = max(0, count_b - pair_count)
    k22 = max(0, total_orders - k11 - k12 - k21)
    return k11, k12, k21, k22


class CoPurchaseMiner:
    """Recomputes observed co-purchase scores for one shop."""

    def __init__(
        self,
        lookback_days: int = LOOKBACK_DAYS,
        max_basket_size: int = MAX_BASKET_SIZE,
        min_pair_count: int = MIN_PAIR_COUNT,
    ):
        self.lookback_days = lookback_days
        self.max_basket_size = max_basket_size
        self.min_pair_count = min_pair_count

    async def run(self, shop_id: str) -> Dict[str, int]:
        """Mine co-purchases and write observed scores. Returns a summary."""
        cutoff = now_utc() - timedelta(days=self.lookback_days)
        params = {
            "shop_id": shop_id,
            "cutoff": cutoff,
            "statuses": list(COUNTED_FINANCIAL_STATUSES),
        }

        async with get_transaction_context() as session:
            total_orders = (
                await session.execute(_TOTAL_SQL, params)
            ).scalar() or 0
            if total_orders == 0:
                logger.info(f"Shop {shop_id}: no orders in window, nothing to mine")
                return {"pairs": 0, "edges_written": 0, "total_orders": 0}

            item_counts = {
                row.product_id: row.order_count
                for row in (await session.execute(_ITEM_SQL, params)).all()
            }
            pairs = (
                await session.execute(
                    _PAIR_SQL,
                    {
                        **params,
                        "max_basket": self.max_basket_size,
                        "min_pair": self.min_pair_count,
                    },
                )
            ).all()

        rows = list(
            self._score_pairs(pairs, item_counts, total_orders, shop_id)
        )
        written = await self._upsert(rows)

        logger.info(
            f"Shop {shop_id}: {len(pairs)} co-purchase pairs over "
            f"{total_orders} orders -> {written} edges updated"
        )
        return {
            "pairs": len(pairs),
            "edges_written": written,
            "total_orders": total_orders,
        }

    def _score_pairs(
        self,
        pairs: Iterable,
        item_counts: Dict[str, int],
        total_orders: int,
        shop_id: str,
    ) -> Iterable[dict]:
        """Score each pair and emit an edge row in both directions.

        Co-purchase is symmetric but the serve path looks up by source, so both
        directions are stored. Only `complement` is mined here — `accessory`,
        `refill` and `substitute` carry semantics that co-occurrence alone
        cannot distinguish, and they come from enrichment or sequence mining.
        """
        for row in pairs:
            a, b, pair_count = row.product_a, row.product_b, row.pair_count
            k = contingency(
                pair_count,
                item_counts.get(a, pair_count),
                item_counts.get(b, pair_count),
                total_orders,
            )
            score = observed_score(*k)
            for source, target in ((a, b), (b, a)):
                yield {
                    "shop_id": shop_id,
                    "source_product_id": source,
                    "target_product_id": target,
                    "edge_type": "complement",
                    "observed_count": pair_count,
                    "observed_llr": score,
                }

    async def _upsert(self, rows: List[dict]) -> int:
        """Write observed scores, then re-blend against whatever prior exists.

        `blended_score` is recomputed in SQL from the post-update row so a pair
        the LLM never predicted still gets a blend (its prior is simply 0), and
        so an existing prior is never overwritten by this job.

        The ramp is deliberately mirrored from `scoring.blend` rather than
        round-tripping every row through Python. The thresholds are passed in
        from the same constants so the two cannot drift apart; see
        `test_sql_blend_mirrors_python_blend` for the shape check.
        """
        if not rows:
            return 0

        written = 0
        async with get_transaction_context() as session:
            for chunk in _chunks(rows, 500):
                stmt = pg_insert(ProductEdge.__table__).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    constraint="pk_product_edges",
                    set_={
                        "observed_count": stmt.excluded.observed_count,
                        "observed_llr": stmt.excluded.observed_llr,
                        "updated_at": now_utc(),
                    },
                )
                await session.execute(stmt)
                written += len(chunk)

            await session.execute(
                _upsert_blend_sql(),
                {
                    "shop_id": rows[0]["shop_id"],
                    "min_obs": BLEND_MIN_OBSERVATIONS,
                    "full_obs": BLEND_FULL_OBSERVATIONS,
                },
            )
        return written


def _upsert_blend_sql():
    """The blend ramp, as a bulk UPDATE.

    Mirrors `scoring.blend` so the whole shop can be re-blended in one
    statement instead of round-tripping every edge through Python. Thresholds
    are bound parameters from the same constants, never literals, so the two
    expressions cannot drift apart.
    """
    return text(
        """
        UPDATE product_edges SET blended_score = CASE
            WHEN observed_count < :min_obs   THEN prior_score
            WHEN observed_count >= :full_obs THEN observed_llr
            ELSE prior_score
                 + (observed_llr - prior_score)
                 * ((observed_count - :min_obs)::real
                    / (:full_obs - :min_obs))
        END
        WHERE shop_id = :shop_id
        """
    )


def _chunks(items: List[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]
