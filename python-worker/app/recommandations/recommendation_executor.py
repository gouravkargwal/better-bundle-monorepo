"""
Recommendation Executor Service
Handles execution of individual recommendation levels and fallback chains
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from app.shared.helpers import now_utc

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.recommandations.user_neighbors import UserNeighborsService
from app.recommandations.frequently_bought_together import (
    FrequentlyBoughtTogetherService,
)
from app.recommandations.recently_viewed import RecentlyViewedService

logger = get_logger(__name__)


class RecommendationExecutor:
    """Service for executing recommendation levels and fallback chains"""

    def __init__(self, gorse_client: GorseApiClient):
        self.gorse_client = gorse_client
        self.user_neighbors_service = UserNeighborsService()

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
            level: Recommendation level to execute
            shop_id: Shop ID
            product_ids: Product IDs
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations
            metadata: Additional metadata
            exclude_items: Items to exclude
            cart_items: Cart items for cart-specific recommendations

        Returns:
            Recommendation result
        """
        try:
            if level == "item_neighbors" and product_ids and len(product_ids) > 0:
                return await self._execute_item_neighbors(
                    shop_id, product_ids[0], category, limit, exclude_items
                )

            elif level == "user_recommendations" and user_id:
                return await self._execute_user_recommendations(
                    shop_id, user_id, category, limit, exclude_items
                )

            elif level == "user_recommendations_category" and user_id:
                # Same as user_recommendations but with explicit category context
                return await self._execute_user_recommendations(
                    shop_id, user_id, category, limit, exclude_items
                )

            elif level == "session_recommendations":
                return await self._execute_session_recommendations(
                    shop_id, user_id, session_id, category, limit, metadata
                )

            elif level == "popular":
                return await self._execute_popular(category, limit)

            elif level == "latest":
                return await self._execute_latest(category, limit)

            elif level == "popular_category":
                return await self._execute_popular_category(category, limit)

            elif level == "user_neighbors" and user_id:
                return await self._execute_user_neighbors(
                    user_id, shop_id, limit, category
                )

            elif level == "frequently_bought_together":
                # Use cart_items if available (cart page), otherwise use product_ids (product page)
                source_items = (
                    cart_items if cart_items and len(cart_items) > 0 else product_ids
                )
                if source_items and len(source_items) > 0:
                    return await self._execute_frequently_bought_together(
                        shop_id, source_items[0], limit
                    )

            elif level == "recently_viewed" and user_id:
                return await self._execute_recently_viewed(shop_id, user_id, limit)

            return {"success": False, "items": [], "source": "none"}

        except Exception as e:
            logger.error(f"Failed to execute recommendation level {level}: {str(e)}")
            return {"success": False, "items": [], "source": "error"}

    async def _execute_item_neighbors(
        self,
        shop_id: str,
        product_id: str,
        category: Optional[str],
        limit: int,
        exclude_items: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Execute item neighbors recommendation"""
        # Apply shop prefix for multi-tenancy
        prefixed_item_id = f"shop_{shop_id}_{product_id}"
        # Convert exclude_items to Gorse format (with shop prefix)
        gorse_exclude_items = None
        if exclude_items:
            gorse_exclude_items = [
                f"shop_{shop_id}_{item_id}" for item_id in exclude_items
            ]

        result = await self.gorse_client.get_item_neighbors(
            item_id=prefixed_item_id,
            n=limit,
            category=category,
            exclude_items=gorse_exclude_items,
        )
        if result["success"]:
            return {
                "success": True,
                "items": result["neighbors"],
                "source": "gorse_item_neighbors",
            }
        return {"success": False, "items": [], "source": "gorse_item_neighbors_failed"}

    async def _execute_user_recommendations(
        self,
        shop_id: str,
        user_id: str,
        category: Optional[str],
        limit: int,
        exclude_items: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Execute user recommendations"""
        # Apply shop prefix for multi-tenancy
        prefixed_user_id = f"shop_{shop_id}_{user_id}"
        # Convert exclude_items to Gorse format (with shop prefix)
        gorse_exclude_items = None
        if exclude_items:
            gorse_exclude_items = [
                f"shop_{shop_id}_{item_id}" for item_id in exclude_items
            ]

        result = await self.gorse_client.get_recommendations(
            user_id=prefixed_user_id,
            n=limit,
            category=category,
            exclude_items=gorse_exclude_items,
        )
        if result["success"]:
            # Filter out empty or invalid recommendations
            valid_recommendations = [
                item
                for item in result["recommendations"]
                if item and str(item).strip() and str(item).strip() != ""
            ]

            if valid_recommendations:
                return {
                    "success": True,
                    "items": valid_recommendations,
                    "source": "gorse_user_recommendations",
                }
            else:
                logger.warning(
                    f"⚠️ User recommendations returned only empty items for user {user_id}"
                )
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_user_recommendations_empty",
                    "error": "All recommendations were empty",
                }
        return {
            "success": False,
            "items": [],
            "source": "gorse_user_recommendations_failed",
        }

    async def _execute_session_recommendations(
        self,
        shop_id: str,
        user_id: Optional[str],
        session_id: Optional[str],
        category: Optional[str],
        limit: int,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute session recommendations"""
        # Apply shop prefix for multi-tenancy
        prefixed_user_id = f"shop_{shop_id}_{user_id}" if user_id else None

        # Build session data as array of feedback objects
        feedback_objects = []
        effective_session_id = session_id or "auto"
        base_feedback = {
            "Comment": f"session_{effective_session_id}",
            "FeedbackType": "view",
            "ItemId": "",
            "Timestamp": now_utc().isoformat(),
            "UserId": prefixed_user_id or "",
        }

        # Add cart contents if available
        if metadata and metadata.get("cart_contents"):
            for item_id in metadata["cart_contents"]:
                cart_feedback = base_feedback.copy()
                cart_feedback["ItemId"] = (
                    f"shop_{shop_id}_{item_id}"  # Apply shop prefix
                )
                cart_feedback["FeedbackType"] = "add_to_cart"
                cart_feedback["Comment"] = f"cart_item_{item_id}"
                feedback_objects.append(cart_feedback)

        # Add recent views if available
        if metadata and metadata.get("recent_views"):
            for item_id in metadata["recent_views"][:5]:  # Limit to 5 recent views
                view_feedback = base_feedback.copy()
                view_feedback["ItemId"] = (
                    f"shop_{shop_id}_{item_id}"  # Apply shop prefix
                )
                view_feedback["FeedbackType"] = "view"
                view_feedback["Comment"] = f"recent_view_{item_id}"
                feedback_objects.append(view_feedback)

        # If no specific items, create a general session feedback
        if not feedback_objects:
            feedback_objects.append(base_feedback)

        result = await self.gorse_client.get_session_recommendations(
            session_data=feedback_objects, n=limit, category=category
        )
        if result["success"]:
            # Handle case where recommendations is None
            recommendations = result.get("recommendations", [])
            if recommendations is None:
                logger.warning(
                    f"⚠️ Session recommendations returned None in fallback chain"
                )
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_session_recommendations_none",
                    "error": "Gorse returned None recommendations",
                }

            # Filter out empty or invalid recommendations
            valid_recommendations = [
                item
                for item in recommendations
                if item and str(item).strip() and str(item).strip() != ""
            ]

            if valid_recommendations:
                return {
                    "success": True,
                    "items": valid_recommendations,
                    "source": "gorse_session_recommendations",
                }
            else:
                logger.warning(f"⚠️ Session recommendations returned only empty items")
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_session_recommendations_empty",
                    "error": "All session recommendations were empty",
                }
        return {
            "success": False,
            "items": [],
            "source": "gorse_session_recommendations_failed",
        }

    async def _execute_popular(
        self, category: Optional[str], limit: int
    ) -> Dict[str, Any]:
        """Execute popular items recommendation"""
        result = await self.gorse_client.get_popular_items(n=limit, category=category)
        if result["success"]:
            # Filter out empty or invalid recommendations
            valid_items = [
                item
                for item in result["items"]
                if item and str(item).strip() and str(item).strip() != ""
            ]

            if valid_items:
                return {
                    "success": True,
                    "items": valid_items,
                    "source": "gorse_popular",
                }
            else:
                logger.warning(f"⚠️ Popular recommendations returned only empty items")
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_popular_empty",
                    "error": "All popular recommendations were empty",
                }
        return {"success": False, "items": [], "source": "gorse_popular_failed"}

    async def _execute_latest(
        self, category: Optional[str], limit: int
    ) -> Dict[str, Any]:
        """Execute latest items recommendation"""
        result = await self.gorse_client.get_latest_items(n=limit, category=category)
        if result["success"]:
            return {
                "success": True,
                "items": result["items"],
                "source": "gorse_latest",
            }
        return {"success": False, "items": [], "source": "gorse_latest_failed"}

    async def _execute_popular_category(
        self, category: Optional[str], limit: int
    ) -> Dict[str, Any]:
        """Execute popular category recommendation"""
        # Use popular items with category filter
        result = await self.gorse_client.get_popular_items(n=limit, category=category)
        if result["success"]:
            return {
                "success": True,
                "items": result["items"],
                "source": "gorse_popular_category",
            }
        return {
            "success": False,
            "items": [],
            "source": "gorse_popular_category_failed",
        }

    async def _execute_user_neighbors(
        self, user_id: str, shop_id: str, limit: int, category: Optional[str]
    ) -> Dict[str, Any]:
        """Execute user neighbors recommendation"""
        result = await self.user_neighbors_service.get_neighbor_recommendations(
            user_id=user_id,
            shop_id=shop_id,
            limit=limit,
            category=category,
        )
        return result

    async def _execute_frequently_bought_together(
        self, shop_id: str, product_id: str, limit: int
    ) -> Dict[str, Any]:
        """Execute frequently bought together recommendation"""
        fbt_service = FrequentlyBoughtTogetherService()
        result = await fbt_service.get_frequently_bought_together(
            shop_id=shop_id,
            product_id=product_id,
            limit=limit,
        )
        return result

    async def _execute_recently_viewed(
        self, shop_id: str, user_id: str, limit: int
    ) -> Dict[str, Any]:
        """Execute recently viewed recommendation"""
        recently_viewed_service = RecentlyViewedService()
        result = await recently_viewed_service.get_recently_viewed_products(
            shop_id=shop_id,
            user_id=user_id,
            limit=limit,
        )
        return result

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

        Args:
            context: Recommendation context
            shop_id: Shop ID
            product_ids: Product IDs
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations
            metadata: Additional metadata
            exclude_items: Items to exclude
            fallback_levels: Custom fallback levels (optional)

        Returns:
            Recommendation result with fallback information
        """
        # Use provided fallback levels or default ones
        if fallback_levels is None:
            fallback_levels = self._get_default_fallback_levels()

        levels = fallback_levels.get(context, ["popular"])

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
                    items = result.get("items", [])
                    items_count = len(items) if items is not None else 0
                    logger.warning(
                        f"⚠️ Level {level} returned no items | context={context} | success={result['success']} | items_count={items_count}"
                    )

            except Exception as e:
                logger.error(
                    f"💥 Level {level} failed | context={context} | error={str(e)}"
                )
                continue

        # All levels failed, return empty results
        logger.warning(
            f"❌ All recommendation levels failed | context={context} | returning empty results"
        )
        return {"success": False, "items": [], "source": "all_failed"}

    def _get_default_fallback_levels(self) -> Dict[str, List[str]]:
        """Get default fallback levels configuration"""
        return {
            "product_page": [
                "frequently_bought_together",  # Level 1: Best for conversion (+11.6% add-to-cart)
                "item_neighbors",  # Level 2: Similar products (always works)
                "user_neighbors",  # Level 3: Social proof (customers also viewed)
                "user_recommendations",  # Level 4: Personalized (if user_id)
                "popular_category",  # Level 5: Fallback
            ],
            "homepage": [
                "recently_viewed",  # Level 1: For returning visitors (continuity)
                "user_recommendations",  # Level 2: Personalized (if user_id)
                "latest",  # Level 3: New arrivals (fresh content)
                "popular",  # Level 4: Best sellers (for new visitors)
            ],
            "cart": [
                "session_recommendations",  # Level 1: Session-based
                "frequently_bought_together",  # Level 2: Cross-sell items
                "user_recommendations",  # Level 3: Personalized
                "popular",  # Level 4: Popular items
            ],
            "profile": [
                "user_recommendations",  # Level 1: Personalized
                "recently_viewed",  # Level 2: Recently viewed items
                "popular",  # Level 3: Popular items
            ],
            "checkout": ["popular"],  # Level 1: Popular items (fast)
            "order_history": [
                "user_recommendations",  # Level 1: Personalized based on order history
                "item_neighbors",  # Level 2: Similar to previously ordered items
                "popular_category",  # Level 3: Popular in categories from order history
                "popular",  # Level 4: General popular items
            ],
            "order_status": [
                "item_neighbors",  # Level 1: Similar to ordered products
                "user_recommendations",  # Level 2: Personalized
                "popular_category",  # Level 3: Popular in same category
                "latest",  # Level 4: New arrivals
            ],
            "collection_page": [
                "popular_category",  # Level 1: Popular in collection category
                "user_recommendations",  # Level 2: Personalized
                "latest",  # Level 3: Latest in category
                "popular",  # Level 4: General popular items
            ],
        }
