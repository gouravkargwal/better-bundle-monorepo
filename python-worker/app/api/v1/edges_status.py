"""
Operational endpoints for the recommendation edge pipeline.

Internal use only — no storefront extension calls these. They exist so an
install can be inspected and re-run without shell access, which matters most
during onboarding: "the widget is empty" needs to be answerable in one request.

Replaces the old `/api/v1/fbt` router, which reported on the FP-Growth model
and cross-encoder that the edge pipeline superseded.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database.session import get_transaction_context
from app.core.config.settings import settings
from app.core.logging import get_logger
from app.recommandations.edges.cooccurrence import CoPurchaseMiner
from app.recommandations.edges.embedding import ProductEmbedder
from app.recommandations.edges.install import EdgeInstallPipeline
from app.recommandations.edges.serving import EdgeRecommender
from app.recommandations.edges.enrichment_store import EnrichmentStore
from app.recommandations.edges.enrichment_sweeper import sweep_once
from app.recommandations.edges.llm_budget import LLMBudget

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/edges", tags=["edges-ops"])


class EdgeStatusResponse(BaseModel):
    shop_id: str
    servable: bool
    products: int = 0
    embedded: int = 0
    total_edges: int = 0
    edges_by_type: Dict[str, int] = {}
    prior_only_edges: int = 0
    observed_edges: int = 0
    last_updated: Optional[str] = None


_STATUS_SQL = text(
    """
    SELECT
      (SELECT COUNT(*) FROM product_data
        WHERE shop_id = :shop_id AND is_active = true)          AS products,
      (SELECT COUNT(*) FROM product_vectors
        WHERE shop_id = :shop_id)                               AS embedded,
      (SELECT COUNT(*) FROM product_edges
        WHERE shop_id = :shop_id)                               AS total_edges,
      (SELECT COUNT(*) FROM product_edges
        WHERE shop_id = :shop_id AND observed_count = 0)        AS prior_only,
      (SELECT COUNT(*) FROM product_edges
        WHERE shop_id = :shop_id AND observed_count > 0)        AS observed,
      (SELECT MAX(updated_at) FROM product_edges
        WHERE shop_id = :shop_id)                               AS last_updated
    """
)

_BY_TYPE_SQL = text(
    """
    SELECT edge_type, COUNT(*) AS n FROM product_edges
    WHERE shop_id = :shop_id GROUP BY edge_type
    """
)


@router.get("/status/{shop_id}", response_model=EdgeStatusResponse)
async def get_edge_status(shop_id: str):
    """What this shop can actually serve, and where the scores came from.

    `prior_only` vs `observed` is the useful split: a healthy new shop is
    almost entirely priors, and a shop with traffic should see `observed`
    climbing. Priors staying at zero means enrichment or embedding failed.
    """
    try:
        async with get_transaction_context() as session:
            row = (await session.execute(_STATUS_SQL, {"shop_id": shop_id})).one()
            by_type = {
                r.edge_type: r.n
                for r in (
                    await session.execute(_BY_TYPE_SQL, {"shop_id": shop_id})
                ).all()
            }

        return EdgeStatusResponse(
            shop_id=shop_id,
            servable=(row.total_edges or 0) > 0,
            products=row.products or 0,
            embedded=row.embedded or 0,
            total_edges=row.total_edges or 0,
            edges_by_type=by_type,
            prior_only_edges=row.prior_only or 0,
            observed_edges=row.observed or 0,
            last_updated=row.last_updated.isoformat() if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"Edge status failed for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install/{shop_id}")
async def run_install(shop_id: str):
    """Run the full install pipeline. Idempotent; safe to re-run."""
    try:
        report = await EdgeInstallPipeline().run(shop_id)
        return report.as_dict()
    except Exception as e:
        logger.error(f"Install failed for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings/{shop_id}")
async def run_embeddings(shop_id: str):
    """Re-embed the catalog. Skips products whose text is unchanged."""
    result = await ProductEmbedder().embed_shop(shop_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "failed"))
    return result


@router.post("/mine/{shop_id}")
async def run_mining(shop_id: str):
    """Re-mine co-purchase LLR from order history and re-blend."""
    try:
        return await CoPurchaseMiner().run(shop_id)
    except Exception as e:
        logger.error(f"Mining failed for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/{shop_id}")
async def preview_recommendations(
    shop_id: str,
    product_ids: str,
    surface: str = "mercury",
    context_value: float = 0.0,
    limit: int = 3,
):
    """What this shop would return for a given cart, without logging anything.

    Deliberately bypasses holdout bucketing and impression logging so that
    debugging a merchant's widget does not pollute their incrementality data.
    """
    ids: List[str] = [p for p in product_ids.split(",") if p.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="product_ids required")

    items: List[Dict[str, Any]] = await EdgeRecommender().recommend(
        shop_id=shop_id,
        context_product_ids=ids,
        surface=surface,
        context_value=context_value,
        limit=limit,
    )
    return {"shop_id": shop_id, "surface": surface, "count": len(items), "items": items}


@router.get("/enrichment/{shop_id}")
async def enrichment_status(shop_id: str):
    """Whether the LLM enrichment actually landed for this shop.

    This endpoint exists because of a real incident: the pipeline reported
    `servable: True` with `prior_edges: 0` for days, because every resolution
    query was failing and the failure was only ever a log line. "Did enrichment
    work?" must be answerable with one request.
    """
    try:
        store = EnrichmentStore(
            model_version=getattr(settings.ml, "AI_CHAT_MODEL", "unknown")
        )
        return {
            "shop_id": shop_id,
            "by_status": await store.stats(shop_id),
            "guards": await LLMBudget().status(),
        }
    except Exception as e:
        logger.error(f"Enrichment status failed for {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrichment/retry")
async def retry_enrichment_now():
    """Run one sweep immediately instead of waiting for the interval.

    The sweeper already runs on a loop; this is for when someone has just
    fixed a key or had quota restored and does not want to wait.
    """
    try:
        return await sweep_once()
    except Exception as e:
        logger.error(f"Manual enrichment sweep failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
