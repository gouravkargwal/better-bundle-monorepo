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

from sqlalchemy import and_, or_, exists, func, select, text

from app.core.database.models.product_edge import ProductEdge
from app.core.database.models.product_data import ProductData
from app.core.database.models.product_vector import ProductVector
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

# Surfaces that render inside checkout have no variant selector, so only
# single-option products can be recommended without asking the shopper to
# pick a variant they cannot see.
CHECKOUT_SURFACES = {"mercury"}

# Table aliases for the candidates query self-join (product_edges appears twice:
# once as the main source, once in the NOT EXISTS substitute veto).
_pe = ProductEdge.__table__.alias("pe")
_pd = ProductData.__table__.alias("pd")
_pe_sub = ProductEdge.__table__.alias("sub")


# ---------------------------------------------------------------------------
# SQLAlchemy Core query builders (replace the old raw text constants)
# ---------------------------------------------------------------------------


def _build_candidates_query(
    shop_id: str,
    context_ids: List[str],
    edge_types: Sequence[str],
    exclude_ids: List[str],
    candidate_limit: int,
) -> Any:
    """Edges → product rows → stock/active filter → substitute veto.

    The NOT EXISTS clause excludes any candidate that has a substitute edge
    pointing at it from any of the context products.

    Uses a ``row_number()`` window function to keep one row per target product
    (the best-scored one), which is the portable equivalent of PostgreSQL's
    ``DISTINCT ON``.
    """
    rn_col = func.row_number().over(
        partition_by=_pe.c.target_product_id,
        order_by=[
            _pe.c.blended_score.desc(),
            _pe.c.observed_count.desc(),
            _pe.c.prior_score.desc(),
        ],
    ).label("rn")

    inner = (
        select(
            _pe.c.target_product_id.label("product_id"),
            _pe.c.edge_type,
            _pe.c.blended_score,
            _pe.c.observed_count,
            _pe.c.prior_score,
            _pd.c.title,
            _pd.c.price,
            _pd.c.product_type,
            _pd.c.total_inventory,
            _pd.c.options,
            rn_col,
        )
        .join(
            _pd,
            and_(
                _pd.c.shop_id == _pe.c.shop_id,
                _pd.c.product_id == _pe.c.target_product_id,
            ),
        )
        .where(
            _pe.c.shop_id == shop_id,
            _pe.c.source_product_id.in_(context_ids),
            _pe.c.edge_type.in_(edge_types),
            or_(
                _pe.c.blended_score > 0,
                _pe.c.observed_count > 0,
                _pe.c.prior_score > 0,
            ),
            _pd.c.is_active == True,  # noqa: E712
            or_(
                _pd.c.total_inventory.is_(None),
                _pd.c.total_inventory > 0,
            ),
            _pe.c.target_product_id.notin_(exclude_ids),
            ~exists(
                select(1)
                .select_from(_pe_sub)
                .where(
                    and_(
                        _pe_sub.c.shop_id == _pe.c.shop_id,
                        _pe_sub.c.edge_type == "substitute",
                        _pe_sub.c.target_product_id == _pe.c.target_product_id,
                        _pe_sub.c.source_product_id.in_(context_ids),
                    )
                )
            ),
        )
    ).subquery()

    return (
        select(
            inner.c.product_id,
            inner.c.edge_type,
            inner.c.blended_score,
            inner.c.observed_count,
            inner.c.prior_score,
            inner.c.title,
            inner.c.price,
            inner.c.product_type,
            inner.c.total_inventory,
            inner.c.options,
        )
        .where(inner.c.rn == 1)
        .order_by(
            inner.c.blended_score.desc(),
            inner.c.observed_count.desc(),
            inner.c.prior_score.desc(),
        )
        .limit(candidate_limit)
    )


def _build_baseline_query(
    shop_id: str,
    edge_types: Sequence[str],
    exclude_ids: List[str],
    candidate_limit: int,
) -> Any:
    """Popular products across all edge types — used when no context is available."""
    return (
        select(
            ProductData.product_id,
            func.max(ProductEdge.edge_type).label("edge_type"),
            func.max(ProductEdge.blended_score).label("blended_score"),
            func.sum(ProductEdge.observed_count).label("observed_count"),
            ProductData.title,
            ProductData.price,
            ProductData.product_type,
            ProductData.total_inventory,
        )
        .join(
            ProductData,
            and_(
                ProductData.shop_id == ProductEdge.shop_id,
                ProductData.product_id == ProductEdge.target_product_id,
            ),
        )
        .where(
            ProductEdge.shop_id == shop_id,
            ProductEdge.edge_type.in_(edge_types),
            ProductData.is_active == True,  # noqa: E712
            or_(
                ProductData.total_inventory.is_(None),
                ProductData.total_inventory > 0,
            ),
            ProductEdge.target_product_id.notin_(exclude_ids),
        )
        .group_by(
            ProductData.product_id,
            ProductData.title,
            ProductData.price,
            ProductData.product_type,
            ProductData.total_inventory,
        )
        .order_by(func.sum(ProductEdge.blended_score).desc())
        .limit(candidate_limit)
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


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


def relevance_score(candidate: Dict[str, Any]) -> float:
    """How relevant this candidate is to the context product.

    Used as the primary ranking signal. Price is intentionally excluded so
    expensive but weakly-related items do not outrank cheaper, better matches.
    """
    score = float(candidate.get("blended_score") or 0.0)
    if score <= 0.0:
        obs = int(candidate.get("observed_count") or 0)
        prior = float(candidate.get("prior_score") or 0.0)
        if obs > 0:
            score = min(0.4, 0.1 * obs)
        elif prior > 0:
            score = prior
        elif candidate.get("source") == "vector":
            score = float(candidate.get("similarity") or 0.2)
    return score


def expected_value(candidate: Dict[str, Any], margin: Optional[float] = None) -> float:
    """Revenue-weighted score: relevance × price × margin.

    Kept for tiebreaking and billing estimates. The serve path no longer sorts
    on this alone, because revenue-weighting can push a weakly-related expensive
    item above a cheaper, better-matched one.
    """
    score = relevance_score(candidate)
    price = float(candidate.get("price") or 0.0)
    return score * price * (margin if margin is not None else 1.0)


def prefer_refills(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Post-purchase ordering: a refill beats an accessory beats a complement.

    Someone who just bought a consumable is the easiest refill sale there is,
    and the plan makes `replenish_days` the signal for exactly this.
    """
    rank = {"refill": 0, "accessory": 1, "complement": 2}
    return sorted(candidates, key=lambda c: rank.get(c.get("edge_type"), 3))


def _is_single_option(candidate: Dict[str, Any]) -> bool:
    """True when the product has zero or one option (no variant picker needed).

    Products with multiple options require a variant selector, which checkout
    and other constrained surfaces cannot render.
    """
    options = candidate.get("options")
    if not options:
        return True
    return len(options) <= 1


# ---------------------------------------------------------------------------
# Vector similarity (kept as raw SQL — pgvector operators and CTE + CROSS JOIN
# are not expressible in SQLAlchemy Core/ORM without losing the HNSW index).
# ---------------------------------------------------------------------------

_VECTOR_NEAREST_SQL = text(
    """
    SELECT pv.product_id
    FROM product_vectors pv
    JOIN product_data pd
      ON pd.shop_id = pv.shop_id AND pd.product_id = pv.product_id
    WHERE pv.shop_id = :shop_id
      AND pv.product_id != :target_id
      AND pd.is_active = true
    ORDER BY pv.vector <=> CAST(:vec AS vector)
    LIMIT :limit
    """
)

_VECTOR_FALLBACK_SQL = text(
    """
    WITH context_vecs AS (
        SELECT vector
        FROM product_vectors
        WHERE shop_id = :shop_id
          AND product_id = ANY(:context_ids)
    )
    SELECT pv.product_id,
           pd.title,
           pd.price,
           pd.product_type,
           pd.options,
           (1.0 - (pv.vector <=> cv.vector)) AS similarity
    FROM context_vecs cv
    CROSS JOIN product_vectors pv
    JOIN product_data pd
      ON pd.shop_id = pv.shop_id AND pd.product_id = pv.product_id
    WHERE pv.shop_id = :shop_id
      AND NOT (pv.product_id = ANY(:exclude_ids))
      AND pd.is_active = true
      AND (pd.total_inventory IS NULL OR pd.total_inventory > 0)
      AND pd.product_type = ANY(:product_types)
    ORDER BY similarity DESC
    LIMIT :limit
    """
)


async def get_visually_similar(
    session: Any = None,
    shop_id: str = "",
    target_product_id: str = "",
    limit: int = 5,
) -> List[str]:
    """Find closest visually/multimodally similar products using pgvector HNSW."""
    if session is None:
        async with get_transaction_context() as sess:
            return await get_visually_similar(sess, shop_id, target_product_id, limit)

    # 1. Get the 1408-D vector for the target product
    target_vector = (
        await session.execute(
            select(ProductVector.vector).where(
                ProductVector.shop_id == shop_id,
                ProductVector.product_id == target_product_id,
            )
        )
    ).scalar_one_or_none()

    if target_vector is None:
        return []

    vec_str = (
        "[" + ",".join(str(float(v)) for v in target_vector) + "]"
        if not isinstance(target_vector, str)
        else target_vector
    )

    rows = (
        await session.execute(
            _VECTOR_NEAREST_SQL,
            {
                "shop_id": shop_id,
                "target_id": target_product_id,
                "vec": vec_str,
                "limit": limit,
            },
        )
    ).all()
    return [row.product_id for row in rows]


# ---------------------------------------------------------------------------
# EdgeRecommender
# ---------------------------------------------------------------------------


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
            # Fall back to visual / multimodal vector similarity before baseline
            candidates = await self._fetch_vector_candidates(shop_id, context_ids, sorted(exclude), limit=CANDIDATE_LIMIT)
            if not candidates:
                logger.info(
                    f"Shop {shop_id}: no edge or vector candidates for {len(context_ids)} "
                    f"context products on {surface}"
                )
                return []
            logger.info(
                f"Shop {shop_id}: serving {len(candidates)} vector similarity candidates for {context_ids}"
            )

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

        # Checkout surfaces have no variant selector — only single-option
        # products can be added to cart without asking the shopper to choose.
        if surface in CHECKOUT_SURFACES:
            single = [c for c in candidates if _is_single_option(c)]
            if single:
                candidates = single
            else:
                logger.info(
                    f"Shop {shop_id}: single-option filter excluded every "
                    f"candidate on {surface}; showing multi-option products"
                )

        margins = margins or {}
        candidates.sort(
            key=lambda c: (
                relevance_score(c),
                float(c.get("price") or 0.0),
            ),
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
            key=lambda c: (
                relevance_score(c),
                float(c.get("price") or 0.0),
            ),
            reverse=True,
        )

        return candidates[:limit]

    async def _fetch_vector_candidates(
        self, shop_id: str, context_ids: List[str], exclude_ids: List[str], limit: int = CANDIDATE_LIMIT
    ) -> List[Dict[str, Any]]:
        """Find candidates using multimodal vector similarity when graph edges are absent.

        Filters by the context products' ``product_type`` so the fallback stays
        within the same category (e.g. shoes → shoes, not shoes → bags).
        """
        async with get_transaction_context() as session:
            # Look up the product_type(s) of the context products so the
            # vector search stays within the same category.
            type_rows = (
                await session.execute(
                    select(ProductData.product_type).where(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(context_ids),
                        ProductData.product_type.isnot(None),
                        ProductData.product_type != "",
                    ).distinct()
                )
            ).all()
            product_types = [r[0] for r in type_rows]

            params: Dict[str, Any] = {
                "shop_id": shop_id,
                "context_ids": context_ids,
                "exclude_ids": exclude_ids or [""],
                "limit": limit,
            }
            if product_types:
                params["product_types"] = product_types
                query = _VECTOR_FALLBACK_SQL
            else:
                # No product_type on context products — fall back to an
                # unfiltered vector search so the widget isn't empty.
                query = text(
                    str(_VECTOR_FALLBACK_SQL).replace(
                        "AND pd.product_type = ANY(:product_types)", ""
                    )
                )

            rows = (await session.execute(query, params)).all()

        seen = set()
        candidates = []
        for r in rows:
            if r.product_id in seen:
                continue
            seen.add(r.product_id)
            sim = float(r.similarity or 0.0)
            candidates.append(
                {
                    "product_id": r.product_id,
                    "edge_type": "complement",
                    "blended_score": max(0.0, sim),
                    "observed_count": 0,
                    "prior_score": max(0.0, sim),
                    "title": r.title,
                    "price": float(r.price or 0.0),
                    "product_type": r.product_type,
                    "options": r.options or [],
                    "similarity": sim,
                    "source": "vector",
                }
            )
        return candidates

    async def _fetch_baseline_candidates(
        self, shop_id: str, exclude_ids: List[str]
    ) -> List[Dict[str, Any]]:
        query = _build_baseline_query(
            shop_id, list(RECOMMENDABLE), exclude_ids, CANDIDATE_LIMIT
        )
        async with get_transaction_context() as session:
            rows = (await session.execute(query)).all()

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
        query = _build_candidates_query(
            shop_id, context_ids, list(RECOMMENDABLE), exclude_ids, CANDIDATE_LIMIT
        )
        async with get_transaction_context() as session:
            rows = (await session.execute(query)).all()

        return [
            {
                "product_id": r.product_id,
                "edge_type": r.edge_type,
                "blended_score": float(r.blended_score or 0.0),
                "observed_count": int(r.observed_count or 0),
                "prior_score": float(getattr(r, "prior_score", 0.0) or 0.0),
                "title": r.title,
                "price": float(r.price or 0.0),
                "product_type": r.product_type,
                "options": r.options or [],
                # Where the score came from, so a merchant asking "why this
                # product?" gets an answer instead of a shrug.
                "source": (
                    "observed"
                    if (r.observed_count or 0) > 0
                    else ("prior" if float(getattr(r, "prior_score", 0.0) or 0.0) > 0 else "observed")
                ),
            }
            for r in rows
        ]
