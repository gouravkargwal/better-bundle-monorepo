from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from app.shared.helpers import now_utc

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.config.settings import settings
from app.shared.constants.interaction_types import (
    GorseFeedbackType,
    map_to_gorse_feedback_type,
)
from app.recommandations.user_neighbors import UserNeighborsService

logger = get_logger(__name__)
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


class HybridRecommendationService:
    """Service to blend multiple recommendation sources for richer results"""

    def __init__(self):
        self.gorse_client = gorse_client

    # Context-specific blending ratios
    BLENDING_RATIOS = {
        "product_page": {
            "item_neighbors": 0.7,  # 70% similar products
            "user_recommendations": 0.3,  # 30% personalized (if user_id available)
        },
        "homepage": {
            "user_recommendations": 0.6,  # 60% personalized
            "popular": 0.4,  # 40% popular items
        },
        "cart": {
            "session_recommendations": 0.5,  # 50% session-based
            "user_recommendations": 0.3,  # 30% personalized
            "popular": 0.2,  # 20% popular items
            "user_neighbors": 0.0,  # 0% neighbor-based (often fails)
        },
        "profile": {
            "user_recommendations": 0.5,  # 50% personalized
            "user_neighbors": 0.3,  # 30% "People like you bought..."
            "popular": 0.2,  # 20% popular items
        },
        "checkout": {"popular": 1.0},  # 100% popular (fast, reliable)
        "order_history": {
            "user_recommendations": 0.6,  # 60% personalized based on order history
            "popular_category": 0.3,  # 30% popular in order history categories
            "popular": 0.1,  # 10% general popular items
        },
        "order_status": {
            "item_neighbors": 0.5,  # 50% similar to ordered products
            "user_recommendations": 0.3,  # 30% personalized
            "popular_category": 0.2,  # 20% popular in same category
        },
        "collection_page": {
            "popular_category": 0.6,  # 60% popular in collection category
            "user_recommendations": 0.3,  # 30% personalized
            "popular": 0.1,  # 10% general popular items
        },
    }

    async def blend_recommendations(
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
    ) -> Dict[str, Any]:
        """
        Blend multiple recommendation sources based on context

        Args:
            context: Recommendation context
            shop_id: Shop ID
            product_id: Product ID
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations
            metadata: Additional metadata

        Returns:
            Blended recommendations result
        """
        try:
            logger.debug(
                f"🔄 Starting hybrid blend | context={context} | shop_id={shop_id} | limit={limit}"
            )
            # Get blending ratios for context
            ratios = self.BLENDING_RATIOS.get(context, {"popular": 1.0})
            logger.debug(f"📊 Blending ratios | context={context} | ratios={ratios}")

            # Collect recommendations from different sources
            all_recommendations = []
            source_info = {}

            # Execute each recommendation source based on ratios
            for source, ratio in ratios.items():
                if ratio <= 0:
                    continue

                # Calculate how many items to get from this source
                source_limit = max(1, int(limit * ratio))
                logger.debug(
                    f"🎯 Getting {source} recommendations | ratio={ratio} | source_limit={source_limit}"
                )

                try:
                    logger.info(
                        f"🎯 Processing source: {source} | session_id={session_id} | user_id={user_id}"
                    )
                    # Get recommendations from this source
                    source_result = await self._get_source_recommendations(
                        source=source,
                        shop_id=shop_id,
                        product_ids=product_ids,
                        user_id=user_id,
                        session_id=session_id,
                        category=category,
                        limit=source_limit,
                        metadata=metadata,
                        exclude_items=exclude_items,
                    )

                    if source_result["success"] and source_result["items"]:
                        # Add source information to each item
                        for item in source_result["items"]:
                            # Handle both string items (item IDs) and dict items
                            if isinstance(item, str):
                                # Skip empty string items
                                if not item or item.strip() == "":
                                    logger.debug(
                                        f"🚫 Skipping empty string item from {source}"
                                    )
                                    continue
                                # Convert string item ID to dict format
                                item_dict = {
                                    "Id": item,
                                    "_source": source,
                                    "_ratio": ratio,
                                }
                            else:
                                # Item is already a dict, check for empty IDs
                                item_id = item.get("Id", item.get("id", ""))
                                if not item_id or str(item_id).strip() == "":
                                    logger.debug(
                                        f"🚫 Skipping empty dict item from {source}: {item}"
                                    )
                                    continue
                                # Item is already a dict, add source info
                                item["_source"] = source
                                item["_ratio"] = ratio
                                item_dict = item

                            all_recommendations.append(item_dict)
                        source_info[source] = {
                            "count": len(source_result["items"]),
                            "ratio": ratio,
                            "success": True,
                        }
                        logger.debug(
                            f"✅ {source} source successful | items={len(source_result['items'])}"
                        )
                    else:
                        source_info[source] = {
                            "count": 0,
                            "ratio": ratio,
                            "success": False,
                            "error": source_result.get("error", "No items returned"),
                        }
                        logger.warning(
                            f"⚠️ {source} source failed | error={source_result.get('error', 'No items returned')}"
                        )

                except Exception as e:
                    logger.warning(
                        f"💥 Failed to get {source} recommendations: {str(e)}"
                    )
                    source_info[source] = {
                        "count": 0,
                        "ratio": ratio,
                        "success": False,
                        "error": str(e),
                    }

            # Deduplicate and blend results
            logger.debug(
                f"🔄 Deduplicating and blending | total_collected={len(all_recommendations)} | target_limit={limit}"
            )
            blended_items = self._deduplicate_and_blend(all_recommendations, limit)
            logger.info(
                f"✅ Hybrid blend complete | final_count={len(blended_items)} | sources_used={len([s for s in source_info.values() if s['success']])}"
            )

            return {
                "success": True,
                "items": blended_items,
                "source": "hybrid",
                "blending_info": {
                    "context": context,
                    "ratios": ratios,
                    "sources": source_info,
                    "total_collected": len(all_recommendations),
                    "final_count": len(blended_items),
                },
            }

        except Exception as e:
            logger.error(f"💥 Failed to blend recommendations: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "hybrid_error",
                "error": str(e),
            }

    async def _get_source_recommendations(
        self,
        source: str,
        shop_id: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get recommendations from a specific source"""

        if source == "item_neighbors" and product_ids:
            # Handle product IDs (single or multiple) - get neighbors for each and blend
            logger.info(f"🔄 Getting item neighbors for products: {product_ids[:3]}...")
            all_neighbors = []

            for pid in product_ids[
                :5
            ]:  # Limit to 5 products to avoid too many API calls
                try:
                    prefixed_item_id = f"shop_{shop_id}_{pid}"
                    # Convert exclude_items to Gorse format (with shop prefix)
                    gorse_exclude_items = None
                    if exclude_items:
                        gorse_exclude_items = [
                            f"shop_{shop_id}_{item_id}" for item_id in exclude_items
                        ]

                    result = await self.gorse_client.get_item_neighbors(
                        item_id=prefixed_item_id,
                        n=limit // len(product_ids) + 2,
                        category=category,
                        exclude_items=gorse_exclude_items,
                    )
                    if result["success"] and result.get("neighbors"):
                        all_neighbors.extend(result["neighbors"])
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get neighbors for product {pid}: {e}")
                    continue

            if all_neighbors:
                # Deduplicate and limit results
                seen_ids = set()
                unique_neighbors = []
                for neighbor in all_neighbors:
                    neighbor_id = neighbor.get("Id", neighbor.get("id", str(neighbor)))
                    if neighbor_id not in seen_ids:
                        seen_ids.add(neighbor_id)
                        unique_neighbors.append(neighbor)
                        if len(unique_neighbors) >= limit:
                            break

                return {
                    "success": True,
                    "items": unique_neighbors,
                    "source": "gorse_item_neighbors",
                }

            return {"success": False, "items": [], "source": "no_neighbors_found"}

        elif source == "user_recommendations" and user_id:
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
            return result
        elif source == "user_recommendations" and not user_id:
            # No user_id provided, skip this source
            logger.debug("⚠️ user_recommendations source skipped: no user_id provided")
            return {
                "success": False,
                "items": [],
                "source": "gorse_user_recommendations_skipped",
                "error": "No user_id provided",
            }

        elif source == "session_recommendations":
            logger.info(
                f"🎯 Processing session_recommendations | session_id={session_id} | user_id={user_id}"
            )
            # Apply shop prefix for multi-tenancy
            prefixed_user_id = f"shop_{shop_id}_{user_id}" if user_id else None

            # We allow session recommendations even without an explicit session_id
            # as long as we have session-derived metadata (cart/recent views/context products).
            has_session_context = False
            if metadata:
                has_session_context = any(
                    bool(metadata.get(key))
                    for key in [
                        "cart_contents",
                        "recent_views",
                        "recent_adds",
                        "cart_data",
                        "product_ids",
                    ]
                )

            # If session_id is missing, synthesize a lightweight one for logging/comment purposes
            effective_session_id = session_id or "auto"

            session_data = self._build_session_data(
                session_id=effective_session_id,
                user_id=prefixed_user_id,
                metadata=metadata,
                shop_id=shop_id,
            )
            logger.info(f"📊 Session data built: {session_data}")

            if not session_data:
                logger.warning(
                    "⚠️ Skipping session_recommendations: no session data available"
                )
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_session_recommendations_skipped",
                    "error": "No session data available",
                }

            result = await self.gorse_client.get_session_recommendations(
                session_data=session_data, n=limit, category=category
            )
            logger.info(f"📊 Session recommendations result: {result}")
            if result.get("success"):
                # Check if we actually got recommendations
                recommendations = result.get("recommendations", [])

                # Handle case where recommendations is None
                if recommendations is None:
                    logger.warning(
                        f"⚠️ Session recommendations returned None | session_data_count={len(session_data)}"
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
                    logger.info(
                        f"✅ Session recommendations successful | count={len(valid_recommendations)}"
                    )
                    return {
                        "success": True,
                        "items": valid_recommendations,
                        "source": "gorse_session_recommendations",
                    }
                logger.warning(
                    f"⚠️ Session recommendations returned empty results | session_data_count={len(session_data)}"
                )
                return {
                    "success": False,
                    "items": [],
                    "source": "gorse_session_recommendations_empty",
                    "error": "No recommendations returned from session data",
                }
            logger.warning(
                f"⚠️ Session recommendations failed | error={result.get('error', 'Unknown error')}"
            )
            return result

        elif source == "popular":
            result = await self.gorse_client.get_popular_items(
                n=limit, category=category
            )
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
                    logger.warning(
                        f"⚠️ Popular recommendations returned only empty items"
                    )
                    return {
                        "success": False,
                        "items": [],
                        "source": "gorse_popular_empty",
                        "error": "All popular recommendations were empty",
                    }
            return result

        elif source == "latest":
            result = await self.gorse_client.get_latest_items(
                n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_latest",
                }
            return result

        elif source == "popular_category":
            result = await self.gorse_client.get_popular_items(
                n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_popular_category",
                }
            return result

        elif source == "user_neighbors" and user_id:
            # Use the UserNeighborsService for collaborative filtering
            user_neighbors_service = UserNeighborsService()
            return await user_neighbors_service.get_neighbor_recommendations(
                user_id=user_id, shop_id=shop_id, limit=limit, category=category
            )

        else:
            return {"success": False, "items": [], "error": f"Invalid source: {source}"}

    def _build_session_data(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        shop_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build session data for Gorse session recommendations as array of feedback objects"""
        feedback_objects = []

        # Create a base feedback object for the session
        base_feedback = {
            "Comment": f"session_{session_id}",
            "FeedbackType": GorseFeedbackType.VIEW,  # Default feedback type
            "ItemId": "",  # Will be filled if we have cart contents
            "Timestamp": now_utc().isoformat(),
            "UserId": user_id or "",
        }

        if metadata:
            # Add cart contents as feedback objects
            if metadata.get("cart_contents"):
                for item_id in metadata["cart_contents"]:
                    cart_feedback = base_feedback.copy()
                    cart_feedback["ItemId"] = (
                        f"shop_{shop_id}_{item_id}" if shop_id else item_id
                    )
                    cart_feedback["FeedbackType"] = GorseFeedbackType.CART_ADD
                    cart_feedback["Comment"] = f"cart_item_{item_id}"
                    feedback_objects.append(cart_feedback)

            # Add recent views as feedback objects
            if metadata.get("recent_views"):
                for item_id in metadata["recent_views"][:10]:  # Last 10
                    view_feedback = base_feedback.copy()
                    view_feedback["ItemId"] = (
                        f"shop_{shop_id}_{item_id}" if shop_id else item_id
                    )
                    view_feedback["FeedbackType"] = GorseFeedbackType.VIEW
                    view_feedback["Comment"] = f"recent_view_{item_id}"
                    feedback_objects.append(view_feedback)

            # Add product context if available (from the current request)
            if metadata.get("product_ids"):
                for product_id in metadata["product_ids"][:5]:  # Limit to 5 products
                    product_feedback = base_feedback.copy()
                    product_feedback["ItemId"] = (
                        f"shop_{shop_id}_{product_id}" if shop_id else product_id
                    )
                    product_feedback["FeedbackType"] = "view"
                    product_feedback["Comment"] = f"context_product_{product_id}"
                    feedback_objects.append(product_feedback)

            # Extract cart contents from behavioral event data if available
            if metadata.get("cart_data") and metadata["cart_data"].get("lines"):
                for line in metadata["cart_data"]["lines"]:
                    if line.get("merchandise", {}).get("product", {}).get("id"):
                        product_id = line["merchandise"]["product"]["id"]
                        cart_feedback = base_feedback.copy()
                        cart_feedback["ItemId"] = (
                            f"shop_{shop_id}_{product_id}" if shop_id else product_id
                        )
                        cart_feedback["FeedbackType"] = GorseFeedbackType.CART_ADD
                        cart_feedback["Comment"] = f"cart_product_{product_id}"
                        feedback_objects.append(cart_feedback)

        # If no specific items, try to get recent user interactions for context
        if not feedback_objects and user_id:
            # Try to get recent user interactions to provide context
            try:
                # This is a fallback - we could enhance this by querying the database
                # for recent user interactions, but for now we'll create a minimal session
                logger.debug(
                    f"🔍 No cart contents found, creating minimal session feedback for user {user_id}"
                )
                minimal_feedback = base_feedback.copy()
                minimal_feedback["Comment"] = f"session_{session_id}_minimal"
                minimal_feedback["FeedbackType"] = "view"
                # Don't add empty ItemId - this causes Gorse to return None
                # Instead, return empty list to indicate no session data
                if not minimal_feedback.get("ItemId"):
                    logger.debug(
                        "⚠️ No meaningful session data available for recommendations"
                    )
                    return []
                feedback_objects.append(minimal_feedback)
            except Exception as e:
                logger.warning(f"⚠️ Failed to create minimal session feedback: {e}")
                feedback_objects.append(base_feedback)
        elif not feedback_objects:
            # No user_id and no cart contents - create basic session feedback
            feedback_objects.append(base_feedback)

        return feedback_objects

    def _deduplicate_and_blend(
        self, all_recommendations: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate and blend recommendations based on source ratios

        Args:
            all_recommendations: List of recommendation items with source info
            limit: Maximum number of recommendations to return

        Returns:
            Deduplicated and blended recommendations
        """
        # Remove duplicates while preserving order
        # Use item ID as the key for deduplication
        seen = set()
        deduplicated = []

        for item in all_recommendations:
            # Handle both string items and dict items
            if isinstance(item, str):
                item_key = item
            else:
                # Use the item ID or the item itself as string for deduplication
                item_key = item.get("Id", item.get("id", str(item)))

            # Skip empty items during deduplication
            if not item_key or str(item_key).strip() == "":
                logger.debug(f"🚫 Skipping empty item during deduplication: {item}")
                continue

            if item_key not in seen:
                seen.add(item_key)
                deduplicated.append(item)

        # Sort by source ratio (higher ratio items first)
        deduplicated.sort(
            key=lambda x: x.get("_ratio", 0) if isinstance(x, dict) else 0,
            reverse=True,
        )

        # Return top items up to limit
        return deduplicated[:limit]
