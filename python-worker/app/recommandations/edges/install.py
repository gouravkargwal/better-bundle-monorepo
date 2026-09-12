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
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from app.core.database.session import get_transaction_context
from app.core.config.settings import settings

from .cooccurrence import CoPurchaseMiner
from .enrichment import EnrichmentService
from .llm_provider import LLMProvider, build_provider
from .enrichment_store import (
    EnrichmentStore,
    retryable_product_ids,
)
from app.core.database.models import MAX_ENRICHMENT_ATTEMPTS
from .resolution import CategoryResolver

logger = logging.getLogger(__name__)


_ACTIVE_PRODUCTS_SQL = text("""
    SELECT product_id, title, description, product_type, vendor, tags, price
    FROM product_data
    WHERE shop_id = :shop_id AND is_active = true
    ORDER BY product_id
    """)


# Above this median pairwise cosine similarity the catalog is one kind of thing
# wearing different titles — wall art, posters, single-line jewellery. The
# enrichment prompt then gets near-identical text for every SKU and returns
# near-identical complement categories, which `resolution.py` grounds against a
# catalog where everything is equally close to everything. The resulting priors
# are not merely weak, they are arbitrary, and they cost an API call per batch
# to produce.
#
# ponytail: one global threshold measured on bge-small. Per-vertical tuning if
# it misfires; the number is a knob, not a law.
HOMOGENEITY_THRESHOLD = 0.75

# Under this many products "everything looks alike" is not a ranking problem —
# there is barely anything to rank — and a small shop needs whatever it can get.
HOMOGENEITY_MIN_PRODUCTS = 20

# Pairs grow quadratically. 60 products is 1,770 comparisons inside Postgres,
# which is cheaper than the single LLM call this decision avoids.
HOMOGENEITY_SAMPLE = 60


_CATALOG_STATS_SQL = text("""
    SELECT (SELECT COUNT(*) FROM product_data
             WHERE shop_id = :shop_id AND is_active = true) AS products,
           (SELECT COUNT(*) FROM product_edges
             WHERE shop_id = :shop_id AND observed_count > 0) AS observed_pairs
    """)

# Median rather than mean: a handful of duplicate listings should not drag a
# genuinely varied catalog over the line.
_MEDIAN_SIMILARITY_SQL = text("""
    WITH sample AS (
        SELECT product_id, vector
        FROM product_vectors
        WHERE shop_id = :shop_id
        ORDER BY random()
        LIMIT :sample_size
    )
    SELECT percentile_cont(0.5) WITHIN GROUP (
               ORDER BY 1 - (a.vector <=> b.vector)
           ) AS median_similarity
    FROM sample a
    JOIN sample b ON a.product_id < b.product_id
    """)


def prior_mode(
    median_similarity: Optional[float],
    product_count: int,
    observed_pairs: int,
) -> str:
    """Which kind of prior this catalog should get.

    "categories" — the default. Complements resolved from LLM category
                   descriptions, which is the right question for a shop selling
                   different kinds of thing.
    "style"      — the catalog is one kind of thing, so the only useful pairing
                   is a second piece that matches the first.
    "none"       — same catalog, but it already has real co-purchase data, so
                   there is nothing for a prior to add and no reason to pay for
                   one.

    Kept pure and separate from the queries so the policy is testable without a
    database, and so the whole decision is readable in one place.
    """
    if median_similarity is None:
        # No vectors, or not enough of them to compare. Unknown is not uniform.
        return "categories"
    if product_count < HOMOGENEITY_MIN_PRODUCTS:
        return "categories"
    if median_similarity < HOMOGENEITY_THRESHOLD:
        return "categories"
    return "none" if observed_pairs > 0 else "style"


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
    # Enrichment bookkeeping, so "did enrichment work?" is answerable from the
    # report rather than by grepping logs.
    enrichment_reused: int = 0
    enrichment_failed: int = 0
    enrichment_dead_lettered: int = 0
    # Which prior strategy the catalog's shape selected. See `prior_mode`.
    prior_mode: str = "categories"
    catalog_similarity: Optional[float] = None
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
            "enrichment_reused": self.enrichment_reused,
            "enrichment_failed": self.enrichment_failed,
            "enrichment_dead_lettered": self.enrichment_dead_lettered,
            "prior_mode": self.prior_mode,
            "catalog_similarity": self.catalog_similarity,
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

        # History first, so the homogeneity check below can see whether this
        # shop has co-purchase edges to fall back on before it decides to spend
        # nothing on enrichment. Backfill does not depend on enrichment.
        mined = await self.backfill_history(shop_id, report)
        report.observed_pairs = mined.get("pairs", 0)
        report.orders_mined = mined.get("total_orders", 0)

        if await self._decide_prior_mode(shop_id, report) != "none":
            enrichments = await self.enrich(shop_id, products, report)
            report.enriched = len(enrichments)

            if enrichments:
                report.prior_edges = await self._resolve(
                    shop_id, report.prior_mode, enrichments
                )
            else:
                report.warnings.append(
                    "enrichment produced nothing; shop has no priors"
                )

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

        # Checked here too, or a uniform catalog quietly pays for enrichment on
        # every `products/update` webhook for the life of the install.
        if await self._decide_prior_mode(shop_id, report) == "none":
            return report

        enrichments = await self.enrich(shop_id, products, report)
        report.enriched = len(enrichments)
        if enrichments:
            if report.prior_mode == "style":
                # Style matching is relative — a new print's neighbours are the
                # rest of the catalog — so re-resolve against every stored
                # descriptor rather than the handful this webhook carried.
                enrichments = await EnrichmentStore(
                    model_version=self._model_version()
                ).load_succeeded(shop_id)
            report.prior_edges = await self._resolve(
                shop_id, report.prior_mode, enrichments
            )
        return report

    # ---------- steps ----------

    async def _resolve(
        self, shop_id: str, mode: str, enrichments: Sequence[Any]
    ) -> int:
        if mode == "style":
            return await self.resolver.resolve_style_affinity(shop_id, enrichments)
        return await self.resolver.resolve_products(shop_id, enrichments)

    async def _decide_prior_mode(self, shop_id: str, report: InstallReport) -> str:
        """Measure the catalog and record which prior strategy it selected.

        Fails open to "categories": any error here leaves the pipeline behaving
        exactly as it did before, because a broken heuristic must not be able to
        switch off a shop's recommendations.
        """
        try:
            async with get_transaction_context() as session:
                stats = (
                    await session.execute(_CATALOG_STATS_SQL, {"shop_id": shop_id})
                ).one()
                row = (
                    await session.execute(
                        _MEDIAN_SIMILARITY_SQL,
                        {"shop_id": shop_id, "sample_size": HOMOGENEITY_SAMPLE},
                    )
                ).one_or_none()
        except Exception as e:
            logger.error(f"Shop {shop_id}: homogeneity check failed: {e}")
            return "categories"

        median = (
            float(row.median_similarity)
            if row is not None and row.median_similarity is not None
            else None
        )
        report.catalog_similarity = median
        report.prior_mode = prior_mode(median, stats.products, stats.observed_pairs)

        if report.prior_mode == "style":
            report.warnings.append(
                f"catalog is near-uniform (median product similarity "
                f"{median:.2f}); pairing on style instead of category"
            )
        elif report.prior_mode == "none":
            report.warnings.append(
                f"catalog is near-uniform (median product similarity "
                f"{median:.2f}); priors skipped as arbitrary, serving "
                "co-purchase edges only"
            )

        if report.prior_mode != "categories":
            logger.info(
                f"Shop {shop_id}: prior mode {report.prior_mode}, median "
                f"similarity {median:.2f} over {stats.products} products with "
                f"{stats.observed_pairs} observed pairs"
            )
        return report.prior_mode

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
        self, shop_id: str, products: Sequence[Dict[str, Any]], report: InstallReport
    ) -> List[Any]:
        """Enrich whatever still needs it, and record every outcome.

        Only products without a current successful row reach the API, so a
        re-run costs nothing for work already done. Failures are written back
        with an attempt count so the sweeper can retry exactly those products.
        """
        store = EnrichmentStore(model_version=self._model_version())

        try:
            to_enrich, already, dead = await store.partition(shop_id, products)
        except Exception as e:
            # Losing the store must not lose the pass; fall back to enriching
            # everything rather than serving a shop with no priors.
            report.warnings.append(f"enrichment store unavailable: {e}")
            logger.error(f"Shop {shop_id}: enrichment store unavailable: {e}")
            to_enrich, already, dead = list(products), [], 0

        report.enrichment_reused = len(already)
        report.enrichment_dead_lettered = dead
        if dead:
            report.warnings.append(
                f"{dead} products gave up after {MAX_ENRICHMENT_ATTEMPTS} "
                "enrichment attempts"
            )

        if not to_enrich:
            logger.info(f"Shop {shop_id}: enrichment up to date, reused {len(already)}")
            return already

        # Claim before calling, so a crash mid-pass leaves PENDING rows the
        # sweeper can find rather than an invisible gap.
        try:
            await store.claim(shop_id, to_enrich)
        except Exception as e:
            logger.error(f"Shop {shop_id}: failed to claim enrichment rows: {e}")

        try:
            service = EnrichmentService(self.provider)
            result = await service.enrich_catalog_with_outcomes(to_enrich)
        except Exception as e:
            # The provider itself is unavailable (no key, total outage). Every
            # claimed product is a failure and must be recorded as one, or the
            # rows sit PENDING forever with no attempt count.
            report.warnings.append(f"enrichment unavailable: {e}")
            logger.error(f"Enrichment unavailable: {e}")
            await self._record_failures(
                store,
                shop_id,
                [str(p.get("product_id")) for p in to_enrich],
                f"{type(e).__name__}: {e}",
                report,
            )
            return already

        try:
            await store.record_success(shop_id, result.enriched)
        except Exception as e:
            logger.error(f"Shop {shop_id}: failed to persist enrichment: {e}")

        for failure in result.failures:
            await self._record_failures(
                store, shop_id, failure.product_ids, failure.error, report
            )

        report.enrichment_failed = len(result.failed_product_ids)
        if report.enrichment_failed:
            report.warnings.append(
                f"{report.enrichment_failed} products fell back to "
                "embedding-only priors and are queued for retry"
            )

        return already + result.enriched

    async def _record_failures(
        self,
        store: "EnrichmentStore",
        shop_id: str,
        product_ids: Sequence[str],
        error: str,
        report: InstallReport,
    ) -> None:
        try:
            await store.record_failure(shop_id, list(product_ids), error)
        except Exception as e:
            # If we cannot even record the failure, say so loudly — this is the
            # one case where work really is lost.
            report.warnings.append(f"could not record enrichment failure: {e}")
            logger.error(f"Shop {shop_id}: could not record enrichment failure: {e}")

    def _model_version(self) -> str:
        return getattr(settings.ml, "AI_CHAT_MODEL", "unknown")

    async def retry_failed_enrichment(self, shop_id: str) -> InstallReport:
        """Retry only the products whose enrichment is outstanding and due.

        Deliberately not a catalog pass: it loads the specific product ids the
        store says are retryable, so a shop with 2,000 products and 20 failures
        costs one API call, not a hundred.
        """
        report = InstallReport(shop_id=shop_id)

        product_ids = await retryable_product_ids(shop_id)
        if not product_ids:
            logger.debug(f"Shop {shop_id}: nothing due for enrichment retry")
            return report

        logger.info(
            f"Shop {shop_id}: retrying enrichment for {len(product_ids)} products"
        )
        return await self.refresh_products(shop_id, product_ids)

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
