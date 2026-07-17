"""
Recommendation Executor Service
Handles execution of individual recommendation levels and fallback chains

Primary engine: TFRS (TensorFlow Recommenders + Vertex AI embeddings)
Emergency airbag: popular (only when TFRS is unavailable)
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from app.shared.helpers import now_utc

from app.core.logging import get_logger
from app.recommandations.tfrs.serving import TfrsServing

logger = get_logger(__name__)


class RecommendationExecutor:
    """Service for executing recommendation levels and fallback chains"""

    def __init__(self, tfrs_serving: Optional[TfrsServing] = None):
        self.tfrs = tfrs_serving or TfrsServing()

    async def execute_recommendation_level(
        self,
        level: str,
        shop_id: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_items: Optional[List[str]] = None,
        cart_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a specific recommendation level

        Args:
            level: Recommendation level to execute ("tfrs" or "popular")
            shop_id: Shop ID
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations
            metadata: Additional metadata
            exclude_items: Items to exclude
            cart_items: Cart items (ignored — TFRS handles all context)

        Returns:
            Recommendation result
        """
        try:
            if level == "tfrs":
                return await self._execute_tfrs(
                    shop_id=shop_id,
                    user_id=user_id,
                    session_id=session_id,
                    context=(
                        metadata.get("context", "checkout") if metadata else "checkout"
                    ),
                    limit=limit,
                    exclude_items=exclude_items,
                )

            elif level == "popular":
                return await self._execute_popular(
                    shop_id=shop_id, limit=limit, exclude_items=exclude_items
                )

            return {"success": False, "items": [], "source": "none"}

        except Exception as e:
            logger.error(f"Failed to execute recommendation level {level}: {str(e)}")
            return {"success": False, "items": [], "source": "error"}

    async def _execute_tfrs(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: str = "checkout",
        limit: int = 6,
        exclude_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute TFRS model for personalized recommendations.

        This is the PRIMARY recommendation engine. Vertex AI embeddings
        handle cold start — no purchase data needed.
        """
        try:
            result = await self.tfrs.recommend(
                shop_id=shop_id,
                user_id=user_id,
                session_id=session_id,
                context=context,
                limit=limit,
                exclude_product_ids=exclude_items,
            )

            if result.get("success") and result.get("items"):
                items = [
                    {
                        "id": item.get("id", item.get("product_id")),
                        "title": item.get("title", ""),
                        "score": item.get("score", 0.0),
                        "price": item.get("price", 0),
                    }
                    for item in result["items"]
                ]

                return {
                    "success": True,
                    "items": items,
                    "source": result.get("source", "tfrs"),
                }

            return {
                "success": False,
                "items": [],
                "source": result.get("source", "tfrs_empty"),
            }

        except Exception as e:
            logger.error(f"TFRS execution failed for shop {shop_id}: {e}")
            return {"success": False, "items": [], "source": "tfrs_error"}

    async def _execute_popular(
        self,
        shop_id: str,
        limit: int = 6,
        exclude_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Emergency fallback: return popular/available products.

        Only fires when TFRS is completely unavailable (model missing,
        API down, corruption, etc.). Uses the TFRS serving's built-in
        popular fallback which queries ProductData directly.
        """
        try:
            result = await self.tfrs.recommend(
                shop_id=shop_id,
                context="popular_fallback",
                limit=limit,
                exclude_product_ids=exclude_items,
            )

            if result.get("success") and result.get("items"):
                items = [
                    {
                        "id": item.get("id", item.get("product_id")),
                        "title": item.get("title", ""),
                        "score": item.get("score", 0.0),
                        "price": item.get("price", 0),
                    }
                    for item in result["items"]
                ]

                return {
                    "success": True,
                    "items": items,
                    "source": "popular",
                }

            return {"success": False, "items": [], "source": "popular_empty"}

        except Exception as e:
            logger.error(f"Popular fallback failed for shop {shop_id}: {e}")
            return {"success": False, "items": [], "source": "popular_error"}

    async def execute_fallback_chain(
        self,
        context: str,
        shop_id: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_items: Optional[List[str]] = None,
        fallback_levels: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the fallback chain for a given context

        TFRS is always tried first. 'popular' is the emergency airbag
        that only fires when TFRS is unavailable.
        """
        if fallback_levels is None:
            fallback_levels = self._get_default_fallback_levels()

        levels = fallback_levels.get(context, ["tfrs", "popular"])

        for i, level in enumerate(levels, 1):
            try:
                logger.debug(
                    f"🎯 Trying level {i}/{len(levels)}: {level} | context={context}"
                )
                result = await self.execute_recommendation_level(
                    level,
                    shop_id,
                    product_ids,
                    user_id,
                    session_id,
                    category,
                    limit,
                    metadata,
                    exclude_items,
                )

                if result["success"] and result.get("items"):
                    return result
                else:
                    items_count = len(result.get("items", []))
                    logger.warning(
                        f"⚠️ Level {level} returned no items | context={context} | success={result['success']} | items_count={items_count}"
                    )

            except Exception as e:
                logger.error(
                    f"💥 Level {level} failed | context={context} | error={str(e)}"
                )
                continue

        logger.warning(
            f"❌ All recommendation levels failed | context={context} | returning empty results"
        )
        return {"success": False, "items": [], "source": "all_failed"}

    def _get_default_fallback_levels(self) -> Dict[str, List[str]]:
        """Get default fallback levels configuration.

        TFRS + Vertex AI embeddings is the ONLY recommendation engine.
        It handles cold start via semantic product understanding.

        'popular' exists only as an emergency airbag — it fires when
        TFRS is unavailable (API down, model corruption, etc.).
        """
        return {
            ctx: ["tfrs", "popular"]
            for ctx in [
                "product_page",
                "homepage",
                "cart",
                "profile",
                "checkout",
                "order_history",
                "order_status",
                "post_purchase",
                "collection_page",
            ]
        }
