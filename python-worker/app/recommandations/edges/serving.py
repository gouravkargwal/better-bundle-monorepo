"""
Serve path (plan section 8). Indexed lookup only — no model, no LLM, no network.

Given what is in the cart (Mercury) or what was just bought (Apollo), read the
precomputed edges, filter them, rank by expected revenue, return two or three.

The filtering and the joins run in Postgres in one query so the request does not
fan out. Ranking runs in Python because it needs the surface's price ceiling and
is a few multiplications over at most 200 rows.

Two rules here are not tuning knobs:

- **Substitutes are excluded, never shown.** An alternative to something already
  in the cart invites a swap at the payment step, which costs the merchant the
  original sale.
- **Nothing already in the cart or order is recommended.** Obvious, but it is
  the single most common way a recommendation widget looks broken.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from app.core.database.session import get_transaction_context

logger = logging.getLogger(__name__)

# Checkout is a low-consideration moment: a costly add-on reads as an
# interruption and risks the whole order. Everything after payment is already
# banked, so the risk tolerance is higher.
#
# Surfaces, and their plan reach:
#   mercury   - checkout UI block. SHOPIFY PLUS ONLY.
#   apollo    - post-purchase interstitial. All plans, but only renders when the
#               card was vaulted, so coverage is partial.
#   thank_you - Thank You / Order Status app block. All plans, no vaulting
#               requirement. The only surface with full reach.
PRICE_CEILING_BY_SURFACE = {
    "mercury": 0.25,    # checkout: low consideration, keep the add-on small
    "apollo": 0.40,     # already paid, higher risk tolerance
    "thank_you": 0.40,  # likewise
    # The storefront surfaces are pre-purchase browsing, not a payment step, so
    # a ceiling relative to cart value is the wrong instrument — a shopper on a
    # product page with an empty cart would see everything filtered out. Left
    # uncapped; `context_value` is usually 0 here anyway, which disables it.
    "phoenix": 1.00,
    "venus": 1.00,
}
DEFAULT_PRICE_CEILING = 0.25

# Read wide, return narrow: filtering happens in SQL, ranking needs headroom.
CANDIDATE_LIMIT = 200
DEFAULT_RETURN_LIMIT = 3

RECOMMENDABLE = ("complement", "accessory", "refill")


# One query: edges -> product rows -> stock/active filter -> substitute veto.
# The NOT EXISTS clause is the substitute exclusion, and it is checked against
# every product in the shopper's context, not just the edge's own source.
_CANDIDATES_SQL = text(
    """
    SELECT DISTINCT ON (pe.target_product_id)
           pe.target_product_id AS product_id,
           pe.edge_type,
           pe.blended_score,
           pe.observed_count,
           pd.title,
           pd.price,
           pd.product_type,
           pd.total_inventory
    FROM product_edges pe
    JOIN product_data pd
      ON pd.shop_id = pe.shop_id AND pd.product_id = pe.target_product_id
    WHERE pe.shop_id = :shop_id
      AND pe.source_product_id = ANY(:context_ids)
      AND pe.edge_type = ANY(:edge_types)
      AND pe.blended_score > 0
      AND pd.is_active = true
      AND (pd.total_inventory IS NULL OR pd.total_inventory > 0)
      AND NOT (pe.target_product_id = ANY(:exclude_ids))
      AND NOT EXISTS (
            SELECT 1 FROM product_edges sub
            WHERE sub.shop_id = pe.shop_id
              AND sub.edge_type = 'substitute'
              AND sub.target_product_id = pe.target_product_id
              AND sub.source_product_id = ANY(:context_ids)
      )
    ORDER BY pe.target_product_id, pe.blended_score DESC
    LIMIT :candidate_limit
    """
)

_BASELINE_SQL = text(
    """
    SELECT pd.product_id,
           MAX(pe.edge_type) AS edge_type,
           MAX(pe.blended_score) AS blended_score,
           SUM(pe.observed_count) AS observed_count,
           pd.title,
           pd.price,
           pd.product_type,
           pd.total_inventory
    FROM product_edges pe
    JOIN product_data pd
      ON pd.shop_id = pe.shop_id AND pd.product_id = pe.target_product_id
    WHERE pe.shop_id = :shop_id
      AND pe.edge_type = ANY(:edge_types)
      AND pd.is_active = true
      AND (pd.total_inventory IS NULL OR pd.total_inventory > 0)
      AND NOT (pe.target_product_id = ANY(:exclude_ids))
    GROUP BY pd.product_id, pd.title, pd.price, pd.product_type, pd.total_inventory
    ORDER BY SUM(pe.blended_score) DESC
    LIMIT :candidate_limit
    """
)


def price_ceiling(surface: str, context_value: float) -> Optional[float]:
    """Maximum price an offer may carry on this surface.

    Returns None when the context value is unknown (zero or missing), because
    a ceiling of zero would filter out every candidate and return an empty
    widget — worse than showing a slightly expensive add-on.
    """
    if not context_value or context_value <= 0:
        return None
    fraction = PRICE_CEILING_BY_SURFACE.get(surface, DEFAULT_PRICE_CEILING)
    return context_value * fraction


def expected_value(candidate: Dict[str, Any], margin: Optional[float] = None) -> float:
    """Rank score: how much revenue this offer is likely to produce.

    `blended_score` stands in for P(add), price for the revenue if added. This
    is the objective that matches revenue-share billing — ranking on similarity
    alone optimises for looking relevant, which is not the same thing.

    Margin is applied when the merchant exposes cost. It usually is not, so the
    default of 1.0 makes this price-weighted, which is why the surface price
    ceiling has to stay in place: without it, price-weighting alone would push
    the most expensive item in the catalog to the top of every checkout.
    """
    score = float(candidate.get("blended_score") or 0.0)
    price = float(candidate.get("price") or 0.0)
    return score * price * (margin if margin is not None else 1.0)


def prefer_refills(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Post-purchase ordering: a refill beats an accessory beats a complement.

    Someone who just bought a consumable is the easiest refill sale there is,
    and the plan makes `replenish_days` the signal for exactly this.
    """
    rank = {"refill": 0, "accessory": 1, "complement": 2}
    return sorted(candidates, key=lambda c: rank.get(c.get("edge_type"), 3))


class EdgeRecommender:
    """Reads precomputed edges and returns offers for one surface."""

    async def recommend(
        self,
        shop_id: str,
        context_product_ids: Sequence[str],
        surface: str,
        context_value: float = 0.0,
        limit: int = DEFAULT_RETURN_LIMIT,
        exclude_product_ids: Optional[Sequence[str]] = None,
        margins: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Return up to `limit` offers, best first.

        `context_product_ids` is the cart contents at checkout, or the purchased
        items post-purchase. `context_value` is the cart subtotal or order total
        and drives the price ceiling.
        """
        context_ids = [str(p) for p in context_product_ids if p]
        if not context_ids:
            return []

        # Never offer back what the shopper already has.
        exclude = set(context_ids) | {str(p) for p in (exclude_product_ids or [])}

        candidates = await self._fetch_candidates(shop_id, context_ids, sorted(exclude))
        if not candidates:
            logger.info(
                f"Shop {shop_id}: no edge candidates for {len(context_ids)} "
                f"context products on {surface}"
            )
            return []

        ceiling = price_ceiling(surface, context_value)
        if ceiling is not None:
            affordable = [
                c for c in candidates if float(c.get("price") or 0.0) <= ceiling
            ]
            # If the ceiling eliminates everything, the shopper still deserves a
            # widget. Fall back to the cheapest candidates rather than nothing.
            if affordable:
                candidates = affordable
            else:
                candidates = sorted(
                    candidates, key=lambda c: float(c.get("price") or 0.0)
                )[:limit]
                logger.info(
                    f"Shop {shop_id}: price ceiling {ceiling:.2f} excluded every "
                    f"candidate on {surface}; falling back to cheapest"
                )

        margins = margins or {}
        candidates.sort(
            key=lambda c: expected_value(c, margins.get(c["product_id"])),
            reverse=True,
        )

        if surface == "apollo":
            # Reorder the already-ranked head so a refill surfaces first.
            head = candidates[: max(limit * 2, limit)]
            candidates = prefer_refills(head) + candidates[len(head) :]

        return candidates[:limit]

    async def recommend_baseline(
        self,
        shop_id: str,
        surface: str,
        context_value: float = 0.0,
        limit: int = DEFAULT_RETURN_LIMIT,
        exclude_product_ids: Optional[Sequence[str]] = None,
        margins: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Return up to `limit` baseline offers, best first."""
        exclude = {str(p) for p in (exclude_product_ids or [])}

        candidates = await self._fetch_baseline_candidates(shop_id, sorted(exclude))
        if not candidates:
            logger.info(f"Shop {shop_id}: no baseline candidates on {surface}")
            return []

        ceiling = price_ceiling(surface, context_value)
        if ceiling is not None:
            affordable = [
                c for c in candidates if float(c.get("price") or 0.0) <= ceiling
            ]
            if affordable:
                candidates = affordable
            else:
                candidates = sorted(
                    candidates, key=lambda c: float(c.get("price") or 0.0)
                )[:limit]
                logger.info(
                    f"Shop {shop_id}: price ceiling {ceiling:.2f} excluded every "
                    f"baseline candidate on {surface}; falling back to cheapest"
                )

        margins = margins or {}
        candidates.sort(
            key=lambda c: expected_value(c, margins.get(c["product_id"])),
            reverse=True,
        )

        return candidates[:limit]

    async def _fetch_baseline_candidates(
        self, shop_id: str, exclude_ids: List[str]
    ) -> List[Dict[str, Any]]:
        async with get_transaction_context() as session:
            rows = (
                await session.execute(
                    _BASELINE_SQL,
                    {
                        "shop_id": shop_id,
                        "edge_types": list(RECOMMENDABLE),
                        "exclude_ids": exclude_ids or [""],
                        "candidate_limit": CANDIDATE_LIMIT,
                    },
                )
            ).all()

        return [
            {
                "product_id": r.product_id,
                "edge_type": r.edge_type,
                "blended_score": float(r.blended_score or 0.0),
                "observed_count": int(r.observed_count or 0),
                "title": r.title,
                "price": float(r.price or 0.0),
                "product_type": r.product_type,
                "source": "observed" if (r.observed_count or 0) >= 5 else "prior",
            }
            for r in rows
        ]

    async def _fetch_candidates(
        self, shop_id: str, context_ids: List[str], exclude_ids: List[str]
    ) -> List[Dict[str, Any]]:
        async with get_transaction_context() as session:
            rows = (
                await session.execute(
                    _CANDIDATES_SQL,
                    {
                        "shop_id": shop_id,
                        "context_ids": context_ids,
                        "edge_types": list(RECOMMENDABLE),
                        "exclude_ids": exclude_ids or [""],
                        "candidate_limit": CANDIDATE_LIMIT,
                    },
                )
            ).all()

        return [
            {
                "product_id": r.product_id,
                "edge_type": r.edge_type,
                "blended_score": float(r.blended_score or 0.0),
                "observed_count": int(r.observed_count or 0),
                "title": r.title,
                "price": float(r.price or 0.0),
                "product_type": r.product_type,
                # Where the score came from, so a merchant asking "why this
                # product?" gets an answer instead of a shrug.
                "source": "observed" if (r.observed_count or 0) >= 5 else "prior",
            }
            for r in rows
        ]
