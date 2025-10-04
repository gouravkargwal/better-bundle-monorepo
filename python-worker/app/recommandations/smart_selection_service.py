"""
Smart Selection Service
Handles intelligent selection of recommendation types based on data availability and context
"""

from typing import Any, Dict, Optional, List

from app.core.logging import get_logger
from app.recommandations.recommendation_executor import RecommendationExecutor

logger = get_logger(__name__)


class SmartSelectionService:
    """Service for intelligently selecting the best recommendation type based on data availability"""

    def __init__(self, recommendation_executor: RecommendationExecutor):
        self.recommendation_executor = recommendation_executor

    async def get_smart_recommendation_type(
        self,
        shop_id: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best recommendation type based on data availability
        Returns the most effective recommendation type that has data
        """
        # Priority order based on conversion effectiveness
        recommendation_types = [
            "frequently_bought_together",  # Best for conversion
            "item_neighbors",  # Always works
            "user_neighbors",  # Social proof
            "user_recommendations",  # Personalized
            "popular_category",  # Fallback
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        product_ids=product_ids,
                        user_id=user_id,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to similar products (always works)
        logger.info("🔄 Smart selection: falling back to similar_products")
        return "item_neighbors"

    async def get_smart_homepage_recommendation_type(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best homepage recommendation type based on visitor type
        Returns the most effective recommendation type for the visitor
        """
        # Priority order based on visitor type and effectiveness
        recommendation_types = [
            "recently_viewed",  # For returning visitors (continuity)
            "user_recommendations",  # Personalized for logged-in users
            "popular",  # Best sellers for new visitors
            "latest",  # New arrivals (fresh content)
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        user_id=user_id,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Homepage smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to popular items (always works for new visitors)
        logger.info("🔄 Homepage smart selection: falling back to popular items")
        return "popular"

    async def get_smart_product_page_recommendation(
        self,
        shop_id: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> dict:
        """
        Get smart recommendation for product page with metadata about selection
        """
        smart_type = await self.get_smart_recommendation_type(
            shop_id=shop_id,
            product_ids=product_ids,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            product_ids=product_ids,
            user_id=user_id,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "reason": (
                "optimal_conversion"
                if smart_type == "frequently_bought_together"
                else "data_availability"
            ),
        }

        return result

    async def get_smart_cart_page_recommendation_type(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best cart page recommendation type
        Returns the most effective recommendation type for cart upsells and cross-sells
        """
        # Priority order based on cart page effectiveness for AOV
        recommendation_types = [
            "frequently_bought_together",  # Primary: Complementary products (AOV focus)
            "item_neighbors",  # Secondary: Similar products (alternative options)
            "user_recommendations",  # Personalized (fallback)
            "popular",  # General popular items (fallback)
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        user_id=user_id,
                        cart_items=cart_items,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Cart smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to popular items (always works)
        logger.info("🔄 Cart smart selection: falling back to popular items")
        return "popular"

    async def get_smart_cart_page_recommendation(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        """
        Get smart cart page recommendation with intelligent type selection
        Focuses on complementary products and upsells to increase AOV
        """
        # Get the smart recommendation type
        smart_type = await self.get_smart_cart_page_recommendation_type(
            shop_id=shop_id,
            cart_items=cart_items,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            user_id=user_id,
            cart_items=cart_items,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "visitor_type": ("returning" if user_id else "new"),
            "cart_context": "upsell_cross_sell",
            "reason": (
                "complementary_products"
                if smart_type == "frequently_bought_together"
                else (
                    "similar_alternatives"
                    if smart_type == "item_neighbors"
                    else (
                        "personalized"
                        if smart_type == "user_recommendations"
                        else "general_popularity"
                    )
                )
            ),
        }

        return result

    async def get_smart_homepage_recommendation(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> dict:
        """
        Get smart recommendation for homepage with metadata about selection
        """
        smart_type = await self.get_smart_homepage_recommendation_type(
            shop_id=shop_id,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            user_id=user_id,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "visitor_type": ("returning" if smart_type == "recently_viewed" else "new"),
            "reason": (
                "returning_visitor"
                if smart_type == "recently_viewed"
                else "new_visitor_or_no_history"
            ),
        }

        return result

    async def get_smart_cart_page_recommendation_type(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best cart page recommendation type
        Returns the most effective recommendation type for cart upsells and cross-sells
        """
        # Priority order based on cart page effectiveness for AOV
        recommendation_types = [
            "frequently_bought_together",  # Primary: Complementary products (AOV focus)
            "item_neighbors",  # Secondary: Similar products (alternative options)
            "user_recommendations",  # Personalized (fallback)
            "popular",  # General popular items (fallback)
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        user_id=user_id,
                        cart_items=cart_items,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Cart smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to popular items (always works)
        logger.info("🔄 Cart smart selection: falling back to popular items")
        return "popular"

    async def get_smart_cart_page_recommendation(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        """
        Get smart cart page recommendation with intelligent type selection
        Focuses on complementary products and upsells to increase AOV
        """
        # Get the smart recommendation type
        smart_type = await self.get_smart_cart_page_recommendation_type(
            shop_id=shop_id,
            cart_items=cart_items,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            user_id=user_id,
            cart_items=cart_items,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "visitor_type": ("returning" if user_id else "new"),
            "cart_context": "upsell_cross_sell",
            "reason": (
                "complementary_products"
                if smart_type == "frequently_bought_together"
                else (
                    "similar_alternatives"
                    if smart_type == "item_neighbors"
                    else (
                        "personalized"
                        if smart_type == "user_recommendations"
                        else "general_popularity"
                    )
                )
            ),
        }

        return result

    async def get_smart_collection_page_recommendation_type(
        self,
        shop_id: str,
        collection_id: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best collection page recommendation type
        Returns the most effective recommendation type for collection browsing
        """
        # Priority order based on collection page effectiveness
        recommendation_types = [
            "popular_category",  # Most popular in category (primary)
            "user_recommendations_category",  # Personalized within category
            "user_recommendations",  # Personalized (fallback)
            "popular",  # General popular items (fallback)
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        user_id=user_id,
                        category=category,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Collection smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to popular items (always works)
        logger.info("🔄 Collection smart selection: falling back to popular items")
        return "popular"

    async def get_smart_collection_page_recommendation(
        self,
        shop_id: str,
        collection_id: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> dict:
        """
        Get smart recommendation for collection page with metadata about selection
        """
        smart_type = await self.get_smart_collection_page_recommendation_type(
            shop_id=shop_id,
            collection_id=collection_id,
            category=category,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            user_id=user_id,
            category=category,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "visitor_type": ("returning" if user_id else "new"),
            "category_context": category or "general",
            "reason": (
                "category_popularity"
                if smart_type == "popular_category"
                else (
                    "personalized_category"
                    if smart_type == "user_recommendations_category"
                    else (
                        "personalized"
                        if smart_type == "user_recommendations"
                        else "general_popularity"
                    )
                )
            ),
        }

        return result

    async def get_smart_cart_page_recommendation_type(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Intelligently determine the best cart page recommendation type
        Returns the most effective recommendation type for cart upsells and cross-sells
        """
        # Priority order based on cart page effectiveness for AOV
        recommendation_types = [
            "frequently_bought_together",  # Primary: Complementary products (AOV focus)
            "item_neighbors",  # Secondary: Similar products (alternative options)
            "user_recommendations",  # Personalized (fallback)
            "popular",  # General popular items (fallback)
        ]

        for rec_type in recommendation_types:
            try:
                # Quick test to see if this type has data
                test_result = (
                    await self.recommendation_executor.execute_recommendation_level(
                        level=rec_type,
                        shop_id=shop_id,
                        user_id=user_id,
                        cart_items=cart_items,
                        limit=1,  # Just test with 1 item
                    )
                )

                if test_result["success"] and test_result.get("items"):
                    logger.info(f"✅ Cart smart selection: {rec_type} has data")
                    return rec_type
                else:
                    logger.debug(f"❌ {rec_type} has no data, trying next...")

            except Exception as e:
                logger.debug(f"⚠️ Error testing {rec_type}: {e}")
                continue

        # Fallback to popular items (always works)
        logger.info("🔄 Cart smart selection: falling back to popular items")
        return "popular"

    async def get_smart_cart_page_recommendation(
        self,
        shop_id: str,
        cart_items: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        """
        Get smart cart page recommendation with intelligent type selection
        Focuses on complementary products and upsells to increase AOV
        """
        # Get the smart recommendation type
        smart_type = await self.get_smart_cart_page_recommendation_type(
            shop_id=shop_id,
            cart_items=cart_items,
            user_id=user_id,
            limit=limit,
        )

        # Execute the smart-selected recommendation type
        result = await self.recommendation_executor.execute_recommendation_level(
            level=smart_type,
            shop_id=shop_id,
            user_id=user_id,
            cart_items=cart_items,
            limit=limit,
        )

        # Add smart selection metadata to result
        result["smart_selection"] = {
            "selected_type": smart_type,
            "visitor_type": ("returning" if user_id else "new"),
            "cart_context": "upsell_cross_sell",
            "reason": (
                "complementary_products"
                if smart_type == "frequently_bought_together"
                else (
                    "similar_alternatives"
                    if smart_type == "item_neighbors"
                    else (
                        "personalized"
                        if smart_type == "user_recommendations"
                        else "general_popularity"
                    )
                )
            ),
        }

        return result
