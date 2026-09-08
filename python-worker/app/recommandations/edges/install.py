"""
Install pipeline (plan section 3) and incremental refresh.

Sequences the pieces so a shop has working recommendations before the merchant
finishes onboarding:

    catalog -> embeddings -> LLM enrichment -> category resolution -> priors
                                                       |
                              order history -> co-purchase LLR -> blend

Steps 1 and 2 already existed (`data collection` consumer and
`cross_encoder_service`); this module adds the ordering, the incremental path,
and the failure semantics.

Failure semantics matter more than speed here. Enrichment is the only step that
depends on a third party, so it is the only step allowed to partially fail: the
products it misses still have embeddings, so they still get resolved against
whatever categories other products produced, and the shop goes live with fewer
priors rather than none. Every other step failing aborts, because a shop marked
live with no edges shows an empty widget, which is the exact failure the
priors-first design exists to prevent.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from app.core.database.session import get_transaction_context
from app.core.config.settings import settings

from .cooccurrence import CoPurchaseMiner
from .enrichment import EnrichmentService
from .llm_provider import LLMProvider, build_provider
from .resolution import CategoryResolver

logger = logging.getLogger(__name__)


_ACTIVE_PRODUCTS_SQL = text(
    """
    SELECT product_id, title, description, product_type, vendor, tags, price
    FROM product_data
    WHERE shop_id = :shop_id AND is_active = true
    ORDER BY product_id
    """
)


@dataclass
class InstallReport:
    """What the install actually managed to do, for logs and the admin UI."""

    shop_id: str
    products: int = 0
    embedded: int = 0
    enriched: int = 0
    prior_edges: int = 0
    observed_pairs: int = 0
    orders_mined: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def is_servable(self) -> bool:
        """Whether this shop can actually return a recommendation.

        Priors alone are enough — that is the point of the design. What is not
        enough is zero edges of any kind.
        """
        return self.prior_edges > 0 or self.observed_pairs > 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "shop_id": self.shop_id,
            "products": self.products,
            "embedded": self.embedded,
            "enriched": self.enriched,
            "prior_edges": self.prior_edges,
            "observed_pairs": self.observed_pairs,
            "orders_mined": self.orders_mined,
            "servable": self.is_servable,
            "warnings": self.warnings,
        }


class EdgeInstallPipeline:
    """Builds a shop's recommendation edges from scratch, or refreshes part."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        resolver: Optional[CategoryResolver] = None,
        miner: Optional[CoPurchaseMiner] = None,
    ):
        self._provider = provider
        self.resolver = resolver or CategoryResolver()
        self.miner = miner or CoPurchaseMiner()

    @property
    def provider(self) -> LLMProvider:
        # Built lazily so a shop with no API key configured still gets the
        # embedding and co-purchase steps instead of failing at construction.
        if self._provider is None:
            self._provider = build_provider(settings)
        return self._provider

    async def run(self, shop_id: str) -> InstallReport:
        """Full install. Returns a report rather than raising on partial success."""
        report = InstallReport(shop_id=shop_id)

        products = await self.load_products(shop_id)
        report.products = len(products)
        if not products:
            report.warnings.append("no active products in catalog")
            logger.warning(f"Shop {shop_id}: install found no active products")
            return report

        report.embedded = await self.ensure_embeddings(shop_id, report)
        enrichments = await self.enrich(products, report)
        report.enriched = len(enrichments)

        if enrichments:
            report.prior_edges = await self.resolver.resolve_products(
                shop_id, enrichments
            )
        else:
            report.warnings.append(
                "enrichment produced nothing; shop has no priors"
            )

        mined = await self.backfill_history(shop_id, report)
        report.observed_pairs = mined.get("pairs", 0)
        report.orders_mined = mined.get("total_orders", 0)

        if not report.is_servable:
            report.warnings.append("shop has no edges and cannot serve")
            logger.error(f"Shop {shop_id}: install completed with zero edges")
        else:
            logger.info(f"Shop {shop_id}: install complete {report.as_dict()}")
        return report

    async def refresh_products(
        self, shop_id: str, product_ids: Sequence[str]
    ) -> InstallReport:
        """Incremental path for `products/create` and `products/update`.

        Re-enriches only the products named, so adding five products costs one
        API call rather than a full catalog pass.
        """
        report = InstallReport(shop_id=shop_id)
        products = await self.load_products(shop_id, list(product_ids))
        report.products = len(products)
        if not products:
            return report

        report.embedded = await self.ensure_embeddings(
            shop_id, report, list(product_ids)
        )
        enrichments = await self.enrich(products, report)
        report.enriched = len(enrichments)
        if enrichments:
            report.prior_edges = await self.resolver.resolve_products(
                shop_id, enrichments
            )
        return report

    # ---------- steps ----------

    async def load_products(
        self, shop_id: str, product_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        sql = str(_ACTIVE_PRODUCTS_SQL)
        params: Dict[str, Any] = {"shop_id": shop_id}
        if product_ids:
            sql = sql.replace(
                "AND is_active = true",
                "AND is_active = true AND product_id = ANY(:product_ids)",
            )
            params["product_ids"] = list(product_ids)

        async with get_transaction_context() as session:
            rows = (await session.execute(text(sql), params)).all()

        return [
            {
                "product_id": r.product_id,
                "title": r.title,
                "description": r.description,
                "product_type": r.product_type,
                "vendor": r.vendor,
                "tags": r.tags,
                "price": float(r.price) if r.price is not None else None,
            }
            for r in rows
        ]

    async def ensure_embeddings(
        self,
        shop_id: str,
        report: InstallReport,
        product_ids: Optional[List[str]] = None,
    ) -> int:
        """Embed anything whose text changed. Idempotent via text_hash."""
        try:
            from .embedding import ProductEmbedder

            result = await ProductEmbedder().embed_shop(
                shop_id=shop_id, product_ids=product_ids
            )
            if not result.get("success"):
                report.warnings.append(
                    f"embedding step reported failure: {result.get('error')}"
                )
            return int(result.get("embedded") or 0)
        except Exception as e:
            # Without vectors, category resolution cannot ground anything, so
            # priors will be empty. Recorded loudly, not swallowed.
            report.warnings.append(f"embedding step failed: {e}")
            logger.error(f"Shop {shop_id}: embedding step failed: {e}")
            return 0

    async def enrich(
        self, products: Sequence[Dict[str, Any]], report: InstallReport
    ) -> List[Any]:
        try:
            service = EnrichmentService(self.provider)
            enrichments = await service.enrich_catalog(products)
        except Exception as e:
            report.warnings.append(f"enrichment unavailable: {e}")
            logger.error(f"Enrichment unavailable: {e}")
            return []

        missing = len(products) - len(enrichments)
        if missing > 0:
            report.warnings.append(
                f"{missing} products fell back to embedding-only priors"
            )
        return enrichments

    async def backfill_history(
        self, shop_id: str, report: InstallReport
    ) -> Dict[str, int]:
        """Seed observed counts from whatever order history the scopes allow.

        A shop with real history starts partly data-driven instead of running
        purely on priors for its first 90 days.
        """
        try:
            return await self.miner.run(shop_id)
        except Exception as e:
            report.warnings.append(f"history backfill failed: {e}")
            logger.error(f"Shop {shop_id}: history backfill failed: {e}")
            return {}
