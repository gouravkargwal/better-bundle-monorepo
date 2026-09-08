"""
Category -> product resolution (plan section 5). No LLM involved.

The enrichment pass says "yoga blocks and props go with this mat". This module
turns that sentence into edges pointing at products that actually exist in the
merchant's catalog: embed the category string with the same local model that
embedded the products, search `product_vectors` for the nearest ones, and write
a `product_edges` row per match.

    prior_score = strength (how reliable the pairing is)
                x similarity (how well this product matches the category)

Both factors are needed. A confident category matched to a poor product is a bad
recommendation, and so is a perfect match on a category the model was unsure
about.

This is the piece that makes install-day recommendations possible, and it is the
same code path as the pre-install bundle report.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database.models.product_edge import ProductEdge
from app.core.database.session import get_transaction_context
from app.shared.helpers import now_utc

from .enrichment import ProductEnrichment

logger = logging.getLogger(__name__)

# Below this cosine similarity the "match" is a different kind of product and
# the edge would be noise. Tuned against the plan's suggested 0.55.
SIMILARITY_THRESHOLD = 0.55

# Products considered per category string.
MATCHES_PER_CATEGORY = 10

# Imported, never redeclared. The model that embedded the products must be the
# model that embeds the category queries searched against them.
from .embedding import EMBEDDING_MODEL  # noqa: E402

# CAST(:query_vec AS vector) rather than `:query_vec::vector`.
#
# Postgres' `::` cast operator collides with SQLAlchemy's `:name` bind-parameter
# syntax inside text(): the parameter was left unbound, Postgres received a
# literal ":" and raised a syntax error on every single query. The failure was
# caught per-product and logged, so the pipeline reported success with
# `prior_edges: 0` — the LLM enrichment was paid for and then thrown away.
_NEAREST_SQL = text(
    """
    SELECT pv.product_id,
           1 - (pv.vector <=> CAST(:query_vec AS vector)) AS similarity
    FROM product_vectors pv
    JOIN product_data pd
      ON pd.shop_id = pv.shop_id AND pd.product_id = pv.product_id
    WHERE pv.shop_id = :shop_id
      AND pd.is_active = true
      AND pd.product_id <> :source_product_id
    ORDER BY pv.vector <=> CAST(:query_vec AS vector)
    LIMIT :limit
    """
)


class CategoryResolver:
    """Resolves enrichment categories into concrete product edges."""

    def __init__(
        self,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        matches_per_category: int = MATCHES_PER_CATEGORY,
        model_name: str = EMBEDDING_MODEL,
    ):
        self.similarity_threshold = similarity_threshold
        self.matches_per_category = matches_per_category
        self.model_name = model_name
        self._encoder = None

    # ---------- embedding ----------

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed category strings with the same model used for products."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading bi-encoder for category resolution: {self.model_name}")
            self._encoder = SentenceTransformer(self.model_name)
        return self._encoder.encode(list(texts)).tolist()

    # ---------- edge construction ----------

    def build_edges(
        self,
        shop_id: str,
        enrichment: ProductEnrichment,
        matches_by_category: Dict[str, List[Tuple[str, float]]],
    ) -> List[dict]:
        """Assemble edge rows for one product from its category matches.

        `matches_by_category` maps a category string to (product_id, similarity)
        pairs already filtered by threshold.
        """
        edges: List[dict] = []
        source = enrichment.product_id

        for complement in enrichment.complement_categories:
            for target, similarity in matches_by_category.get(complement.category, []):
                edges.append(
                    self._edge(
                        shop_id,
                        source,
                        target,
                        # An accessory is a complement that depends on the source
                        # product. The serve path ranks both, so the distinction
                        # only shapes the post-purchase preference order.
                        "accessory" if enrichment.role == "accessory" else "complement",
                        complement.strength * similarity,
                        f"{complement.category} @ {similarity:.2f}",
                    )
                )

        if enrichment.substitute_category:
            for target, similarity in matches_by_category.get(
                enrichment.substitute_category, []
            ):
                edges.append(
                    self._edge(
                        shop_id,
                        source,
                        target,
                        # Written to be EXCLUDED at serve time, never shown.
                        # Showing an alternative at the payment step causes
                        # swaps and abandonment.
                        "substitute",
                        similarity,
                        f"substitute: {enrichment.substitute_category} @ {similarity:.2f}",
                    )
                )

        # A consumable points at itself: the offer is "buy this again", which is
        # what makes the post-purchase surface work for refills.
        if enrichment.role == "consumable" and enrichment.replenish_days:
            edges.append(
                self._edge(
                    shop_id,
                    source,
                    source,
                    "refill",
                    1.0,
                    f"consumable, ~{enrichment.replenish_days}d",
                )
            )

        return _dedupe_keep_strongest(edges)

    def _edge(
        self,
        shop_id: str,
        source: str,
        target: str,
        edge_type: str,
        prior: float,
        reason: str,
    ) -> dict:
        return {
            "shop_id": shop_id,
            "source_product_id": source,
            "target_product_id": target,
            "edge_type": edge_type,
            "prior_score": max(0.0, min(1.0, float(prior))),
            "prior_reason": reason[:500],
        }

    # ---------- database ----------

    async def find_matches(
        self, shop_id: str, source_product_id: str, categories: Sequence[str]
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Nearest active products for each category string, thresholded."""
        categories = [c for c in dict.fromkeys(categories) if c]
        if not categories:
            return {}

        vectors = self.embed(categories)
        out: Dict[str, List[Tuple[str, float]]] = {}

        async with get_transaction_context() as session:
            for category, vector in zip(categories, vectors):
                rows = (
                    await session.execute(
                        _NEAREST_SQL,
                        {
                            "shop_id": shop_id,
                            "source_product_id": source_product_id,
                            "query_vec": _to_pgvector(vector),
                            "limit": self.matches_per_category,
                        },
                    )
                ).all()
                out[category] = [
                    (r.product_id, float(r.similarity))
                    for r in rows
                    if r.similarity is not None
                    and float(r.similarity) >= self.similarity_threshold
                ]
        return out

    async def resolve_products(
        self, shop_id: str, enrichments: Sequence[ProductEnrichment]
    ) -> int:
        """Resolve and persist priors for a set of enriched products."""
        all_edges: List[dict] = []
        for enrichment in enrichments:
            categories = [c.category for c in enrichment.complement_categories]
            if enrichment.substitute_category:
                categories.append(enrichment.substitute_category)
            try:
                matches = await self.find_matches(
                    shop_id, enrichment.product_id, categories
                )
            except Exception as e:
                logger.error(
                    f"Resolution failed for {enrichment.product_id}: {e}"
                )
                continue
            all_edges.extend(self.build_edges(shop_id, enrichment, matches))

        written = await self.persist(all_edges)
        logger.info(
            f"Shop {shop_id}: resolved {len(enrichments)} products -> "
            f"{written} prior edges"
        )
        return written

    async def persist(self, edges: List[dict]) -> int:
        """Upsert priors.

        Only the prior columns are touched. `observed_count` and `observed_llr`
        belong to the co-purchase miner, and overwriting them here would throw
        away real evidence every time a product was re-enriched.
        """
        if not edges:
            return 0

        async with get_transaction_context() as session:
            for chunk in _chunk(edges, 500):
                stmt = pg_insert(ProductEdge.__table__).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    constraint="pk_product_edges",
                    set_={
                        "prior_score": stmt.excluded.prior_score,
                        "prior_reason": stmt.excluded.prior_reason,
                        "updated_at": now_utc(),
                    },
                )
                await session.execute(stmt)

            # A brand-new edge has no observations, so its blend is its prior.
            # Existing rows keep whatever the miner last computed.
            await session.execute(
                text(
                    """
                    UPDATE product_edges
                    SET blended_score = prior_score
                    WHERE shop_id = :shop_id AND observed_count = 0
                    """
                ),
                {"shop_id": edges[0]["shop_id"]},
            )
        return len(edges)


def _dedupe_keep_strongest(edges: List[dict]) -> List[dict]:
    """One row per (source, target, type), keeping the highest prior.

    Two different categories can both resolve to the same product; the stronger
    reason should win rather than whichever happened to be processed last.
    """
    best: Dict[Tuple[str, str, str], dict] = {}
    for e in edges:
        key = (e["source_product_id"], e["target_product_id"], e["edge_type"])
        if key not in best or e["prior_score"] > best[key]["prior_score"]:
            best[key] = e
    return list(best.values())


def _to_pgvector(vector: Sequence[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


def _chunk(items: List[dict], size: int) -> Iterable[List[dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
