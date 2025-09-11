"""
Recommendation API endpoints
Handles all recommendation requests from Shopify extension with context-based routing
"""

import asyncio
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query, Header, Request
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.database.simple_db_client import get_database
from app.core.config.settings import settings
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

# Initialize Gorse client
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


# Pydantic models for request/response
class RecommendationRequest(BaseModel):
    """Request model for recommendations"""

    shop_domain: str = Field(..., description="Shop domain")
    context: str = Field(
        ..., description="Context: product_page, homepage, cart, profile, checkout"
    )
    product_id: Optional[str] = Field(
        None, description="Product ID for product-specific recommendations"
    )
    user_id: Optional[str] = Field(
        None, description="User ID for personalized recommendations"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID for session-based recommendations"
    )
    category: Optional[str] = Field(None, description="Category filter")
    limit: int = Field(default=6, ge=1, le=20, description="Number of recommendations")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""

    success: bool
    recommendations: List[Dict[str, Any]]
    count: int
    source: str  # "gorse", "fallback", "database"
    context: str
    shop_id: str
    user_id: Optional[str] = None
    timestamp: datetime


class ProductEnrichment:
    """Service to enrich Gorse item IDs with Shopify product data"""

    def __init__(self):
        self.db = None

    async def get_database(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    async def enrich_items(
        self,
        shop_id: str,
        item_ids: List[str],
        context: str = "product_page",
        source: str = "unknown",
    ) -> List[Dict[str, Any]]:
        """
        Enrich Gorse item IDs with Shopify product data

        Args:
            shop_id: Shop ID
            item_ids: List of Gorse item IDs (which are Shopify product IDs)

        Returns:
            List of enriched product data
        """
        try:
            db = await self.get_database()

            # Fetch products from database
            products = await db.productdata.find_many(
                where={
                    "shopId": shop_id,
                    "productId": {"in": item_ids},
                    "isActive": True,
                },
                select={
                    "productId": True,
                    "title": True,
                    "handle": True,
                    "price": True,
                    "compareAtPrice": True,
                    "imageUrl": True,
                    "imageAlt": True,
                    "totalInventory": True,
                    "status": True,
                    "productType": True,
                    "vendor": True,
                },
            )

            # Create a mapping for quick lookup
            product_map = {p["productId"]: p for p in products}

            # Enrich items in the same order as requested
            enriched_items = []
            for item_id in item_ids:
                if item_id in product_map:
                    product = product_map[item_id]
                    # Only include essential fields that Phoenix extension actually uses
                    enriched_items.append(
                        {
                            "title": product["title"],
                            "handle": product["handle"],
                            "price": product["price"],
                            "currency": "USD",  # TODO: Get from shop settings
                            "image": product["imageUrl"],
                            "imageAlt": product["imageAlt"],
                            "reason": self._get_recommendation_reason(context, source),
                        }
                    )
                else:
                    # Item not found in database, skip it
                    logger.warning(
                        f"Product {item_id} not found in database for shop {shop_id}"
                    )

            return enriched_items

        except Exception as e:
            logger.error(f"Failed to enrich items: {str(e)}")
            return []

    def _get_recommendation_reason(self, context: str, source: str) -> str:
        """Get contextual recommendation reason based on context and source"""

        # More specific reasons based on ML source
        if "item_neighbors" in source:
            return "Similar products"
        elif "user_recommendations" in source:
            return "Recommended for you"
        elif "session_recommendations" in source:
            return "Based on your browsing"
        elif "popular" in source:
            return "Popular choice"
        elif "latest" in source:
            return "New arrival"
        elif "fallback" in source:
            return "Trending now"
        else:
            # Context-based fallback reasons
            context_reasons = {
                "product_page": "Customers also bought",
                "homepage": "Featured product",
                "cart": "Perfect addition",
                "profile": "Just for you",
                "checkout": "Don't miss out",
            }
            return context_reasons.get(context, "Recommended for you")


# Initialize enrichment service
enrichment_service = ProductEnrichment()


class CategoryDetectionService:
    """Service to auto-detect product categories with caching"""

    def __init__(self):
        self.db = None
        self.redis_client = None

    async def get_database(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def get_product_category(
        self, product_id: str, shop_id: str
    ) -> Optional[str]:
        """
        Get product category with Redis caching

        Args:
            product_id: Product ID
            shop_id: Shop ID

        Returns:
            Product category (productType or first collection) or None
        """
        try:
            # Create cache key
            cache_key = f"product_category:{shop_id}:{product_id}"

            # Check cache first
            redis_client = await self.get_redis_client()
            cached_category = await redis_client.get(cache_key)
            if cached_category:
                logger.debug(f"Category cache hit for product {product_id}")
                return (
                    cached_category.decode("utf-8")
                    if isinstance(cached_category, bytes)
                    else cached_category
                )

            # Query database
            db = await self.get_database()
            product = await db.productdata.find_unique(
                where={"shopId": shop_id, "productId": product_id},
                select={"productType": True, "collections": True},
            )

            category = None
            if product:
                # Prioritize productType over collections
                if product["productType"]:
                    category = product["productType"]
                elif product["collections"] and len(product["collections"]) > 0:
                    # Use first collection as category
                    category = (
                        product["collections"][0].get("title")
                        if isinstance(product["collections"][0], dict)
                        else str(product["collections"][0])
                    )

            # Cache for 1 hour (3600 seconds)
            if category:
                await redis_client.setex(cache_key, 3600, category)
                logger.debug(f"Cached category '{category}' for product {product_id}")

            return category

        except Exception as e:
            logger.error(f"Failed to get product category: {str(e)}")
            return None


class RecommendationCacheService:
    """Service to handle recommendation caching with context-specific TTL"""

    def __init__(self):
        self.redis_client = None

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    # Context-specific TTL configuration
    CACHE_TTL = {
        "product_page": 1800,  # 30 minutes (product-specific)
        "homepage": 3600,  # 1 hour (general)
        "cart": 300,  # 5 minutes (dynamic)
        "profile": 900,  # 15 minutes (user-specific)
        "checkout": 0,  # No cache (fast, fresh)
    }

    def generate_cache_key(
        self,
        shop_id: str,
        context: str,
        product_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
    ) -> str:
        """
        Generate a unique cache key for recommendations

        Args:
            shop_id: Shop ID
            context: Recommendation context
            product_id: Product ID
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations

        Returns:
            Cache key string
        """
        # Create a deterministic key based on all parameters
        key_parts = [
            "recommendations",
            shop_id,
            context,
            str(product_id or ""),
            str(user_id or ""),
            str(session_id or ""),
            str(category or ""),
            str(limit),
        ]

        # Join and hash to create a consistent key
        key_string = ":".join(key_parts)
        return f"rec:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def get_cached_recommendations(
        self, cache_key: str, context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached recommendations if available

        Args:
            cache_key: Cache key
            context: Recommendation context

        Returns:
            Cached recommendations or None
        """
        try:
            # Skip caching for checkout context
            if self.CACHE_TTL[context] == 0:
                return None

            redis_client = await self.get_redis_client()
            cached_data = await redis_client.get(cache_key)

            if cached_data:
                logger.debug(f"Recommendation cache hit for context {context}")
                return json.loads(
                    cached_data.decode("utf-8")
                    if isinstance(cached_data, bytes)
                    else cached_data
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get cached recommendations: {str(e)}")
            return None

    async def cache_recommendations(
        self, cache_key: str, recommendations: Dict[str, Any], context: str
    ) -> None:
        """
        Cache recommendations with context-specific TTL

        Args:
            cache_key: Cache key
            recommendations: Recommendations data to cache
            context: Recommendation context
        """
        try:
            # Skip caching for checkout context
            if self.CACHE_TTL[context] == 0:
                return

            redis_client = await self.get_redis_client()
            ttl = self.CACHE_TTL[context]

            # Add metadata to cached data
            cached_data = {
                "recommendations": recommendations,
                "cached_at": datetime.now().isoformat(),
                "context": context,
                "ttl": ttl,
            }

            await redis_client.setex(cache_key, ttl, json.dumps(cached_data))
            logger.debug(
                f"Cached recommendations for context {context} with TTL {ttl}s"
            )

        except Exception as e:
            logger.error(f"Failed to cache recommendations: {str(e)}")


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
        },
        "profile": {
            "user_recommendations": 0.5,  # 50% personalized
            "user_neighbors": 0.3,  # 30% "People like you bought..."
            "popular": 0.2,  # 20% popular items
        },
        "checkout": {"popular": 1.0},  # 100% popular (fast, reliable)
    }

    async def blend_recommendations(
        self,
        context: str,
        shop_id: str,
        product_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        metadata: Optional[Dict[str, Any]] = None,
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
            # Get blending ratios for context
            ratios = self.BLENDING_RATIOS.get(context, {"popular": 1.0})

            # Collect recommendations from different sources
            all_recommendations = []
            source_info = {}

            # Execute each recommendation source based on ratios
            for source, ratio in ratios.items():
                if ratio <= 0:
                    continue

                # Calculate how many items to get from this source
                source_limit = max(1, int(limit * ratio))

                try:
                    # Get recommendations from this source
                    source_result = await self._get_source_recommendations(
                        source=source,
                        shop_id=shop_id,
                        product_id=product_id,
                        user_id=user_id,
                        session_id=session_id,
                        category=category,
                        limit=source_limit,
                        metadata=metadata,
                    )

                    if source_result["success"] and source_result["items"]:
                        # Add source information to each item
                        for item in source_result["items"]:
                            item["_source"] = source
                            item["_ratio"] = ratio

                        all_recommendations.extend(source_result["items"])
                        source_info[source] = {
                            "count": len(source_result["items"]),
                            "ratio": ratio,
                            "success": True,
                        }
                    else:
                        source_info[source] = {
                            "count": 0,
                            "ratio": ratio,
                            "success": False,
                            "error": source_result.get("error", "No items returned"),
                        }

                except Exception as e:
                    logger.warning(f"Failed to get {source} recommendations: {str(e)}")
                    source_info[source] = {
                        "count": 0,
                        "ratio": ratio,
                        "success": False,
                        "error": str(e),
                    }

            # Deduplicate and blend results
            blended_items = self._deduplicate_and_blend(all_recommendations, limit)

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
            logger.error(f"Failed to blend recommendations: {str(e)}")
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
        product_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get recommendations from a specific source"""

        if source == "item_neighbors" and product_id:
            return await self.gorse_client.get_item_neighbors(
                item_id=product_id, n=limit, category=category
            )

        elif source == "user_recommendations" and user_id:
            return await self.gorse_client.get_recommendations(
                user_id=user_id, n=limit, category=category
            )

        elif source == "session_recommendations" and session_id:
            session_data = self._build_session_data(session_id, user_id, metadata)
            return await self.gorse_client.get_session_recommendations(
                session_data=session_data, n=limit, category=category
            )

        elif source == "popular":
            return await self.gorse_client.get_popular_items(n=limit, category=category)

        elif source == "latest":
            return await self.gorse_client.get_latest_items(n=limit, category=category)

        elif source == "user_neighbors" and user_id:
            # Use the UserNeighborsService for collaborative filtering
            from app.api.v1.recommendations import user_neighbors_service

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
    ) -> Dict[str, Any]:
        """Build session data for Gorse session recommendations"""
        session_data = {
            "SessionId": session_id,
            "UserId": user_id,
            "Timestamp": datetime.now().isoformat(),
        }

        if metadata:
            # Add cart contents for upsells
            if metadata.get("cart_contents"):
                session_data["Items"] = metadata["cart_contents"]

            # Add recent views for browsing history
            if metadata.get("recent_views"):
                session_data["RecentViews"] = metadata["recent_views"][:10]  # Last 10

            # Add device type for mobile optimization
            if metadata.get("device_type"):
                session_data["DeviceType"] = metadata["device_type"]

            # Add custom metadata
            if metadata.get("custom_data"):
                session_data["CustomData"] = metadata["custom_data"]

        return session_data

    def _deduplicate_and_blend(
        self, all_recommendations: List[str], limit: int
    ) -> List[str]:
        """
        Deduplicate and blend recommendations based on source ratios

        Args:
            all_recommendations: List of recommendation items with source info
            limit: Maximum number of recommendations to return

        Returns:
            Deduplicated and blended recommendations
        """
        # Remove duplicates while preserving order
        seen = set()
        deduplicated = []

        for item in all_recommendations:
            if item not in seen:
                seen.add(item)
                deduplicated.append(item)

        # Sort by source ratio (higher ratio items first)
        deduplicated.sort(key=lambda x: x.get("_ratio", 0), reverse=True)

        # Return top items up to limit
        return deduplicated[:limit]


class UserNeighborsService:
    """Service to handle user neighbors and their purchase data for collaborative filtering"""

    def __init__(self):
        self.gorse_client = gorse_client
        self.db = None
        self.redis_client = None

    async def get_database(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def get_neighbor_recommendations(
        self, user_id: str, shop_id: str, limit: int = 6, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recommendations based on similar users' purchases

        Args:
            user_id: User ID to find neighbors for
            shop_id: Shop ID
            limit: Number of recommendations to return
            category: Category filter

        Returns:
            Dict with neighbor-based recommendations
        """
        try:
            # Get user neighbors from Gorse
            neighbors_result = await self.gorse_client.get_user_neighbors(user_id, n=10)

            if not neighbors_result["success"] or not neighbors_result["neighbors"]:
                logger.warning(f"No user neighbors found for user {user_id}")
                return {
                    "success": False,
                    "items": [],
                    "source": "user_neighbors_empty",
                    "error": "No user neighbors found",
                }

            # Extract neighbor user IDs
            neighbor_user_ids = [
                neighbor.get("Id", neighbor)
                for neighbor in neighbors_result["neighbors"]
            ]
            logger.debug(f"Found {len(neighbor_user_ids)} neighbors for user {user_id}")

            # Get recent purchases from neighbor users
            neighbor_items = await self._get_neighbor_purchases(
                neighbor_user_ids, shop_id, category, limit * 2  # Get more to filter
            )

            if not neighbor_items:
                logger.warning(f"No neighbor purchases found for user {user_id}")
                return {
                    "success": False,
                    "items": [],
                    "source": "user_neighbors_no_purchases",
                    "error": "No neighbor purchases found",
                }

            # Remove duplicates and limit results
            unique_items = list(
                dict.fromkeys(neighbor_items)
            )  # Preserve order, remove duplicates
            final_items = unique_items[:limit]

            logger.info(
                f"Generated {len(final_items)} neighbor-based recommendations for user {user_id}"
            )

            return {
                "success": True,
                "items": final_items,
                "source": "user_neighbors",
                "neighbor_count": len(neighbor_user_ids),
                "purchase_count": len(neighbor_items),
            }

        except Exception as e:
            logger.error(f"Failed to get neighbor recommendations: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "user_neighbors_error",
                "error": str(e),
            }

    async def _get_neighbor_purchases(
        self,
        neighbor_user_ids: List[str],
        shop_id: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[str]:
        """
        Get recent purchases from neighbor users

        Args:
            neighbor_user_ids: List of neighbor user IDs
            shop_id: Shop ID
            category: Category filter
            limit: Maximum number of items to return

        Returns:
            List of product IDs from neighbor purchases
        """
        try:
            db = await self.get_database()

            # Query recent orders from neighbor users
            # We'll look at orders from the last 90 days to get recent purchases
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=90)

            # Get orders from neighbor users
            orders = await db.orderdata.find_many(
                where={
                    "shopId": shop_id,
                    "customerId": {"in": neighbor_user_ids},
                    "createdAt": {"gte": cutoff_date},
                },
                select={"lineItems": True},
                take=limit * 2,  # Get more orders to ensure we have enough items
                order_by={"createdAt": "desc"},
            )

            # Extract product IDs from order line items
            product_ids = []
            for order in orders:
                if order.get("lineItems"):
                    for line_item in order["lineItems"]:
                        if isinstance(line_item, dict) and line_item.get("productId"):
                            product_ids.append(line_item["productId"])
                        elif isinstance(line_item, str):
                            # Handle case where lineItems might be stored differently
                            product_ids.append(line_item)

            # If we have category filter, filter products by category
            if category and product_ids:
                filtered_products = await self._filter_products_by_category(
                    product_ids, shop_id, category
                )
                return filtered_products[:limit]

            return product_ids[:limit]

        except Exception as e:
            logger.error(f"Failed to get neighbor purchases: {str(e)}")
            return []

    async def _filter_products_by_category(
        self, product_ids: List[str], shop_id: str, category: str
    ) -> List[str]:
        """
        Filter products by category

        Args:
            product_ids: List of product IDs to filter
            shop_id: Shop ID
            category: Category to filter by

        Returns:
            List of product IDs matching the category
        """
        try:
            db = await self.get_database()

            # Get products and filter by category
            products = await db.productdata.find_many(
                where={
                    "shopId": shop_id,
                    "productId": {"in": product_ids},
                    "OR": [
                        {"productType": {"contains": category, "mode": "insensitive"}},
                        {"collections": {"has": category}},
                    ],
                },
                select={"productId": True},
            )

            return [product["productId"] for product in products]

        except Exception as e:
            logger.error(f"Failed to filter products by category: {str(e)}")
            return product_ids  # Return original list if filtering fails


class RecommendationAnalytics:
    """Service to track recommendation performance and analytics"""

    def __init__(self):
        self.redis_client = None

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def log_recommendation_request(
        self,
        shop_id: str,
        context: str,
        source: str,
        count: int,
        user_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """
        Log recommendation request for analytics

        Args:
            shop_id: Shop ID
            context: Recommendation context
            source: Recommendation source (gorse, cache, fallback, etc.)
            count: Number of recommendations returned
            user_id: User ID (if available)
            product_id: Product ID (if available)
            category: Category (if available)
        """
        try:
            redis_client = await self.get_redis_client()

            # Create analytics data
            analytics_data = {
                "timestamp": datetime.now().isoformat(),
                "shop_id": shop_id,
                "context": context,
                "source": source,
                "count": count,
                "user_id": user_id,
                "product_id": product_id,
                "category": category,
            }

            # Store in Redis with TTL (keep for 30 days)
            analytics_key = (
                f"analytics:recommendations:{datetime.now().strftime('%Y-%m-%d')}"
            )
            await redis_client.lpush(analytics_key, json.dumps(analytics_data))
            await redis_client.expire(analytics_key, 30 * 24 * 3600)  # 30 days

            logger.debug(
                f"Logged recommendation analytics: {context} -> {source} ({count} items)"
            )

        except Exception as e:
            logger.error(f"Failed to log recommendation analytics: {str(e)}")


# Initialize services
category_service = CategoryDetectionService()
cache_service = RecommendationCacheService()
hybrid_service = HybridRecommendationService()
analytics_service = RecommendationAnalytics()
user_neighbors_service = UserNeighborsService()


async def get_fallback_recommendations(
    shop_id: str, n: int = 10, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get fallback recommendations when Gorse is unavailable

    Args:
        shop_id: Shop ID
        n: Number of recommendations
        category: Optional category filter

    Returns:
        List of fallback recommendations
    """
    try:
        db = await get_database()

        # Build where clause
        where_clause = {
            "shopId": shop_id,
            "isActive": True,
            "totalInventory": {"gt": 0},
        }

        if category:
            where_clause["productType"] = category

        # Get popular products as fallback
        products = await db.productdata.find_many(
            where=where_clause,
            take=n,
            order_by={"totalInventory": "desc"},
            select={
                "productId": True,
                "title": True,
                "handle": True,
                "price": True,
                "compareAtPrice": True,
                "imageUrl": True,
                "imageAlt": True,
                "totalInventory": True,
                "status": True,
                "productType": True,
                "vendor": True,
            },
        )

        return [
            {
                "item_id": p["productId"],
                "product_id": p["productId"],
                "title": p["title"],
                "handle": p["handle"],
                "price": p["price"],
                "compare_at_price": p["compareAtPrice"],
                "image_url": p["imageUrl"],
                "image_alt": p["imageAlt"],
                "inventory": p["totalInventory"],
                "status": p["status"],
                "product_type": p["productType"],
                "vendor": p["vendor"],
                "available": (
                    p["totalInventory"] > 0 if p["totalInventory"] is not None else True
                ),
                "source": "fallback",
            }
            for p in products
        ]

    except Exception as e:
        logger.error(f"Failed to get fallback recommendations: {str(e)}")
        return []


# Context-based routing logic
FALLBACK_LEVELS = {
    "product_page": [
        "item_neighbors",  # Level 1: Similar products
        "user_recommendations",  # Level 2: Personalized (if user_id)
        "popular_category",  # Level 3: Popular in category
    ],
    "homepage": [
        "user_recommendations",  # Level 1: Personalized
        "popular",  # Level 2: Popular items
        "latest",  # Level 3: Latest items
    ],
    "cart": [
        "session_recommendations",  # Level 1: Session-based
        "user_recommendations",  # Level 2: Personalized
        "popular",  # Level 3: Popular items
    ],
    "profile": [
        "user_recommendations",  # Level 1: Personalized
        "popular",  # Level 2: Popular items
    ],
    "checkout": ["popular"],  # Level 1: Popular items (fast)
}


async def execute_recommendation_level(
    level: str,
    shop_id: str,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 6,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute a specific recommendation level

    Args:
        level: Recommendation level to execute
        shop_id: Shop ID
        product_id: Product ID
        user_id: User ID
        session_id: Session ID
        category: Category filter
        limit: Number of recommendations
        metadata: Additional metadata

    Returns:
        Recommendation result
    """
    try:
        if level == "item_neighbors" and product_id:
            result = await gorse_client.get_item_neighbors(
                item_id=product_id, n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["neighbors"],
                    "source": "gorse_item_neighbors",
                }

        elif level == "user_recommendations" and user_id:
            result = await gorse_client.get_recommendations(
                user_id=user_id, n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["recommendations"],
                    "source": "gorse_user_recommendations",
                }

        elif level == "session_recommendations" and session_id:
            session_data = {
                "SessionId": session_id,
                "UserId": user_id,
                "Timestamp": datetime.now().isoformat(),
            }

            # Add cart contents if available
            if metadata and metadata.get("cart_contents"):
                session_data["Items"] = metadata["cart_contents"]

            result = await gorse_client.get_session_recommendations(
                session_data=session_data, n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["recommendations"],
                    "source": "gorse_session_recommendations",
                }

        elif level == "popular":
            result = await gorse_client.get_popular_items(n=limit, category=category)
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_popular",
                }

        elif level == "latest":
            result = await gorse_client.get_latest_items(n=limit, category=category)
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_latest",
                }

        elif level == "popular_category":
            # This is handled by the popular level with category filter
            return await execute_recommendation_level(
                "popular",
                shop_id,
                product_id,
                user_id,
                session_id,
                category,
                limit,
                metadata,
            )

        return {"success": False, "items": [], "source": "none"}

    except Exception as e:
        logger.error(f"Failed to execute recommendation level {level}: {str(e)}")
        return {"success": False, "items": [], "source": "error"}


async def execute_fallback_chain(
    context: str,
    shop_id: str,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 6,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute the fallback chain for a given context

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
        Recommendation result with fallback information
    """
    levels = FALLBACK_LEVELS.get(context, ["popular"])

    for level in levels:
        try:
            result = await execute_recommendation_level(
                level,
                shop_id,
                product_id,
                user_id,
                session_id,
                category,
                limit,
                metadata,
            )

            if result["success"] and result["items"]:
                logger.info(
                    f"Recommendation level {level} succeeded for context {context}"
                )
                return result
            else:
                logger.warning(
                    f"Recommendation level {level} returned no items for context {context}"
                )

        except Exception as e:
            logger.error(
                f"Recommendation level {level} failed for context {context}: {str(e)}"
            )
            continue

    # All levels failed, use database fallback
    logger.warning(
        f"All recommendation levels failed for context {context}, using database fallback"
    )
    fallback_items = await get_fallback_recommendations(shop_id, limit, category)

    return {"success": True, "items": fallback_items, "source": "database_fallback"}


@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """
    Get recommendations based on context with intelligent fallback system

    This endpoint provides context-aware recommendations using Gorse ML models
    with automatic fallbacks when Gorse is unavailable.

    Features:
    - Auto category detection from product_id
    - Context-specific caching with Redis
    - Performance optimization for checkout context
    """
    try:
        # Validate context
        valid_contexts = ["product_page", "homepage", "cart", "profile", "checkout"]
        if request.context not in valid_contexts:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid context. Must be one of: {valid_contexts}",
            )

        # Validate shop exists
        db = await get_database()
        shop = await db.shop.find_unique(where={"shopDomain": request.shop_domain})
        if not shop:
            raise HTTPException(
                status_code=404, detail=f"Shop {request.shop_domain} not found"
            )

        # Auto-detect category if missing and product_id is provided
        category = request.category
        if not category and request.product_id:
            logger.debug(f"Auto-detecting category for product {request.product_id}")
            category = await category_service.get_product_category(
                request.product_id, shop.id
            )
            if category:
                logger.info(
                    f"Auto-detected category '{category}' for product {request.product_id}"
                )

        # Generate cache key
        cache_key = cache_service.generate_cache_key(
            shop_id=shop.id,
            context=request.context,
            product_id=request.product_id,
            user_id=request.user_id,
            session_id=request.session_id,
            category=category,
            limit=request.limit,
        )

        # Check cache first (skip for checkout context)
        cached_result = await cache_service.get_cached_recommendations(
            cache_key, request.context
        )
        if cached_result:
            logger.info(
                f"Returning cached recommendations for context {request.context}"
            )
            return RecommendationResponse(
                success=True,
                recommendations=cached_result["recommendations"],
                count=len(cached_result["recommendations"]),
                source="cache",
                context=request.context,
                shop_id=shop.id,
                user_id=request.user_id,
                timestamp=datetime.now(),
            )

        # Performance optimization for checkout context
        if request.context == "checkout":
            # Limit recommendations for speed
            request.limit = min(request.limit, 3)
            logger.debug(
                f"Optimized checkout context: limited to {request.limit} recommendations"
            )

        # Try hybrid recommendations first (except for checkout which uses simple fallback)
        if request.context != "checkout":
            logger.debug(
                f"Attempting hybrid recommendations for context {request.context}"
            )
            result = await hybrid_service.blend_recommendations(
                context=request.context,
                shop_id=shop.id,
                product_id=request.product_id,
                user_id=request.user_id,
                session_id=request.session_id,
                category=category,  # Use auto-detected category
                limit=request.limit,
                metadata=request.metadata,
            )

            # If hybrid recommendations fail or return insufficient results, fall back to simple chain
            if (
                not result["success"]
                or len(result.get("items", [])) < request.limit // 2
            ):
                logger.warning(
                    f"Hybrid recommendations insufficient, falling back to simple chain"
                )
                result = await execute_fallback_chain(
                    context=request.context,
                    shop_id=shop.id,
                    product_id=request.product_id,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    category=category,
                    limit=request.limit,
                    metadata=request.metadata,
                )
        else:
            # For checkout, use simple fallback chain for speed
            result = await execute_fallback_chain(
                context=request.context,
                shop_id=shop.id,
                product_id=request.product_id,
                user_id=request.user_id,
                session_id=request.session_id,
                category=category,
                limit=request.limit,
                metadata=request.metadata,
            )

        if not result["success"] or not result["items"]:
            # Final fallback: return empty recommendations
            return RecommendationResponse(
                success=True,
                recommendations=[],
                count=0,
                source="empty",
                context=request.context,
                shop_id=shop.id,
                user_id=request.user_id,
                timestamp=datetime.now(),
            )

        # Enrich with Shopify product data
        item_ids = result["items"]
        enriched_items = await enrichment_service.enrich_items(
            shop.id, item_ids, request.context, result["source"]
        )

        # Prepare response data
        response_data = {
            "recommendations": enriched_items,
            "count": len(enriched_items),
            "source": result["source"],
            "context": request.context,
            "shop_id": shop.id,
            "user_id": request.user_id,
            "timestamp": datetime.now().isoformat(),
            "category_detected": category if not request.category else None,
        }

        # Cache the results (skip for checkout context)
        await cache_service.cache_recommendations(
            cache_key, response_data, request.context
        )

        # Log analytics (async, non-blocking)
        asyncio.create_task(
            analytics_service.log_recommendation_request(
                shop_id=shop.id,
                context=request.context,
                source=result["source"],
                count=len(enriched_items),
                user_id=request.user_id,
                product_id=request.product_id,
                category=category,
            )
        )

        return RecommendationResponse(
            success=True,
            recommendations=enriched_items,
            count=len(enriched_items),
            source=result["source"],
            context=request.context,
            shop_id=shop.id,
            user_id=request.user_id,
            timestamp=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {str(e)}"
        )


@router.get("/health")
async def recommendations_health_check():
    """
    Health check for the recommendations system including cache and category services
    """
    try:
        # Check Gorse health
        gorse_health = await gorse_client.health_check()

        # Check database connection
        db = await get_database()
        await db.shop.find_first()  # Simple query to test connection

        # Check Redis cache connection
        redis_client = await get_redis_client()
        await redis_client.ping()  # Test Redis connection

        # Check cache TTL configuration
        cache_ttl_status = {
            context: f"{ttl}s" if ttl > 0 else "disabled"
            for context, ttl in cache_service.CACHE_TTL.items()
        }

        return {
            "success": True,
            "status": "healthy",
            "gorse": gorse_health,
            "database": "connected",
            "redis_cache": "connected",
            "cache_ttl_config": cache_ttl_status,
            "services": {
                "category_detection": "available",
                "recommendation_caching": "available",
                "product_enrichment": "available",
                "hybrid_recommendations": "available",
                "user_neighbors": "available",
                "analytics": "available",
            },
            "blending_ratios": hybrid_service.BLENDING_RATIOS,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Recommendations health check failed: {str(e)}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(),
        }
