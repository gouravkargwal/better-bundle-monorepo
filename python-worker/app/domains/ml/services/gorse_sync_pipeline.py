"""
Complete Gorse Data Synchronization Pipeline
Uses ALL feature tables to build comprehensive user and item profiles
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseSyncPipeline:
    """
    Synchronizes data from ALL feature tables to Gorse-compatible format
    """

    def __init__(self):
        self._db_client = None

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def sync_all(self, shop_id: str):
        """
        Main entry point - syncs all data for a shop to Gorse
        """
        try:
            logger.info(f"Starting Gorse sync for shop: {shop_id}")

            # 1. Sync Users (combining multiple feature tables)
            await self.sync_users(shop_id)

            # 2. Sync Items (combining multiple feature tables)
            await self.sync_items(shop_id)

            # 3. Sync Feedback (from events, orders, and interaction features)
            await self.sync_feedback(shop_id)

            logger.info(f"Completed Gorse sync for shop: {shop_id}")

        except Exception as e:
            logger.error(f"Failed to sync shop {shop_id}: {str(e)}")
            raise

    async def sync_users(self, shop_id: str):
        """
        Sync users combining UserFeatures, CustomerBehaviorFeatures, and InteractionFeatures
        """
        try:
            db = await self._get_database()

            # Query all user-related features using proper Prisma syntax
            query = """
                SELECT 
                    uf.*,
                    cbf."engagementScore",
                    cbf."recencyScore", 
                    cbf."diversityScore",
                    cbf."behavioralScore",
                    cbf."sessionCount",
                    cbf."productViewCount",
                    cbf."cartAddCount",
                    cbf."purchaseCount" as cbf_purchase_count,
                    cbf."searchCount",
                    cbf."uniqueProductsViewed",
                    cbf."uniqueCollectionsViewed",
                    cbf."deviceType",
                    cbf."primaryReferrer",
                    cbf."browseToCartRate",
                    cbf."cartToPurchaseRate",
                    cbf."searchToPurchaseRate",
                    cbf."mostActiveHour",
                    cbf."mostActiveDay",
                    -- Aggregate interaction features
                    COALESCE(
                        (SELECT SUM("interactionScore") 
                         FROM "InteractionFeatures" 
                         WHERE "customerId" = uf."customerId" 
                         AND "shopId" = uf."shopId"), 
                        0
                    ) as total_interaction_score,
                    COALESCE(
                        (SELECT AVG("affinityScore") 
                         FROM "InteractionFeatures" 
                         WHERE "customerId" = uf."customerId" 
                         AND "shopId" = uf."shopId"), 
                        0
                    ) as avg_affinity_score,
                    -- Session features aggregation
                    COALESCE(
                        (SELECT COUNT(*) 
                         FROM "SessionFeatures" 
                         WHERE "customerId" = uf."customerId" 
                         AND "shopId" = uf."shopId" 
                         AND "checkoutCompleted" = true), 
                        0
                    ) as completed_sessions,
                    COALESCE(
                        (SELECT AVG("durationSeconds") 
                         FROM "SessionFeatures" 
                         WHERE "customerId" = uf."customerId" 
                         AND "shopId" = uf."shopId"), 
                        0
                    ) as avg_session_duration
                FROM "UserFeatures" uf
                LEFT JOIN "CustomerBehaviorFeatures" cbf 
                    ON uf."customerId" = cbf."customerId" 
                    AND uf."shopId" = cbf."shopId"
                WHERE uf."shopId" = $1
            """

            result = await db.query_raw(query, shop_id)
            users = [dict(row) for row in result] if result else []

            for user in users:
                labels = self._build_comprehensive_user_labels(user)

                # Upsert to GorseUsers
                await self._upsert_gorse_user(
                    user_id=user["customer_id"], shop_id=shop_id, labels=labels
                )

            # Also sync anonymous session users
            await self._sync_anonymous_users(shop_id)

            logger.info(f"Synced {len(users)} users for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to sync users: {str(e)}")
            raise

    async def sync_items(self, shop_id: str):
        """
        Sync items combining ProductFeatures, CollectionFeatures, ProductCollectionFeatures
        """
        try:
            db = await self._get_database()

            # Query all product-related features using proper Prisma syntax
            query = """
                SELECT 
                    pf.*,
                    pd."status",
                    pd."productType",
                    pd."vendor",
                    pd."tags",
                    pd."collections",
                    pd."totalInventory",
                    pd."compareAtPrice",
                    -- Product-Collection features
                    pcf."collectionCount",
                    pcf."collectionQualityScore",
                    pcf."crossCollectionScore",
                    pcf."isInManualCollections",
                    pcf."isInAutomatedCollections",
                    -- Co-purchase strength (from ProductPairFeatures)
                    COALESCE(
                        (SELECT AVG("liftScore") 
                         FROM "ProductPairFeatures" 
                         WHERE ("productId1" = pf."productId" OR "productId2" = pf."productId")
                         AND "shopId" = pf."shopId"), 
                        0
                    ) as avg_lift_score,
                    COALESCE(
                        (SELECT COUNT(DISTINCT CASE 
                            WHEN "productId1" = pf."productId" THEN "productId2" 
                            ELSE "productId1" END) 
                         FROM "ProductPairFeatures" 
                         WHERE ("productId1" = pf."productId" OR "productId2" = pf."productId")
                         AND "coPurchaseCount" > 0
                         AND "shopId" = pf."shopId"), 
                        0
                    ) as frequently_bought_with_count,
                    -- Search performance
                    COALESCE(
                        (SELECT AVG("clickThroughRate") 
                         FROM "SearchProductFeatures" 
                         WHERE "productId" = pf."productId" 
                         AND "shopId" = pf."shopId"), 
                        0
                    ) as search_ctr,
                    COALESCE(
                        (SELECT AVG("conversionRate") 
                         FROM "SearchProductFeatures" 
                         WHERE "productId" = pf."productId" 
                         AND "shopId" = pf."shopId"), 
                        0
                    ) as search_conversion_rate
                FROM "ProductFeatures" pf
                JOIN "ProductData" pd 
                    ON pf."productId" = pd."productId" 
                    AND pf."shopId" = pd."shopId"
                LEFT JOIN "ProductCollectionFeatures" pcf
                    ON pf."productId" = pcf."productId"
                    AND pf."shopId" = pcf."shopId"
                WHERE pf."shopId" = $1
                    AND pd."isActive" = true
            """

            result = await db.query_raw(query, shop_id)
            products = [dict(row) for row in result] if result else []

            for product in products:
                labels = self._build_comprehensive_item_labels(product)
                categories = await self._get_product_categories(product, shop_id)
                is_hidden = self._should_hide_product(product)

                # Upsert to GorseItems
                await self._upsert_gorse_item(
                    item_id=product["product_id"],
                    shop_id=shop_id,
                    categories=categories,
                    labels=labels,
                    is_hidden=is_hidden,
                )

            logger.info(f"Synced {len(products)} items for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to sync items: {str(e)}")
            raise

    async def sync_feedback(self, shop_id: str, since_hours: int = 24):
        """
        Sync feedback from behavioral events, orders, and interaction features
        """
        try:
            since_time = now_utc() - timedelta(hours=since_hours)

            # 1. Process behavioral events
            events_feedback = await self._process_behavioral_events(shop_id, since_time)

            # 2. Process orders
            orders_feedback = await self._process_orders(shop_id, since_time)

            # 3. Process interaction features (for weighted feedback)
            interaction_feedback = await self._process_interaction_features(
                shop_id, since_time
            )

            # 4. Process session-based feedback
            session_feedback = await self._process_session_feedback(shop_id, since_time)

            # Combine all feedback
            all_feedback = (
                events_feedback
                + orders_feedback
                + interaction_feedback
                + session_feedback
            )

            # Deduplicate and insert
            unique_feedback = self._deduplicate_feedback(all_feedback)

            for feedback in unique_feedback:
                await self._insert_gorse_feedback(feedback)

            logger.info(
                f"Synced {len(unique_feedback)} feedback records for shop {shop_id}"
            )

        except Exception as e:
            logger.error(f"Failed to sync feedback: {str(e)}")
            raise

    def _build_comprehensive_user_labels(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build comprehensive Gorse user labels from all feature tables
        """
        labels = {
            # From UserFeatures
            "total_purchases": int(user.get("totalPurchases", 0)),
            "total_spent": float(user.get("totalSpent", 0)),
            "avg_order_value": float(user.get("avgOrderValue", 0)),
            "lifetime_value": float(user.get("lifetimeValue", 0)),
            "days_since_last_order": user.get("daysSinceLastOrder"),
            "order_frequency_per_month": float(user.get("orderFrequencyPerMonth", 0)),
            "distinct_products_purchased": int(
                user.get("distinctProductsPurchased", 0)
            ),
            "distinct_categories_purchased": int(
                user.get("distinctCategoriesPurchased", 0)
            ),
            "preferred_category": user.get("preferredCategory", "unknown"),
            "preferred_vendor": user.get("preferredVendor", "unknown"),
            "price_preference": user.get("pricePointPreference", "mid"),
            "discount_sensitivity": float(user.get("discountSensitivity", 0)),
            # From CustomerBehaviorFeatures
            "engagement_score": float(user.get("engagementScore", 0)),
            "recency_score": float(user.get("recencyScore", 0)),
            "diversity_score": float(user.get("diversityScore", 0)),
            "behavioral_score": float(user.get("behavioralScore", 0)),
            "session_count": int(user.get("sessionCount", 0)),
            "product_view_count": int(user.get("productViewCount", 0)),
            "cart_add_count": int(user.get("cartAddCount", 0)),
            "search_count": int(user.get("searchCount", 0)),
            "unique_products_viewed": int(user.get("uniqueProductsViewed", 0)),
            "unique_collections_viewed": int(user.get("uniqueCollectionsViewed", 0)),
            "browse_to_cart_rate": (
                float(user.get("browseToCartRate", 0))
                if user.get("browseToCartRate")
                else 0
            ),
            "cart_to_purchase_rate": (
                float(user.get("cartToPurchaseRate", 0))
                if user.get("cartToPurchaseRate")
                else 0
            ),
            "search_to_purchase_rate": (
                float(user.get("searchToPurchaseRate", 0))
                if user.get("searchToPurchaseRate")
                else 0
            ),
            "most_active_hour": user.get("mostActiveHour"),
            "most_active_day": user.get("mostActiveDay"),
            "device_type": user.get("deviceType", "unknown"),
            "primary_referrer": user.get("primaryReferrer", "direct"),
            # From aggregated InteractionFeatures
            "total_interaction_score": float(user.get("total_interaction_score", 0)),
            "avg_affinity_score": float(user.get("avg_affinity_score", 0)),
            # From aggregated SessionFeatures
            "completed_sessions": int(user.get("completed_sessions", 0)),
            "avg_session_duration": float(user.get("avg_session_duration", 0)),
            # Computed segments
            "customer_segment": self._calculate_customer_segment(user),
            "is_active": bool(user.get("daysSinceLastOrder", 365) < 30),
            "is_high_value": bool(user.get("lifetimeValue", 0) > 500),
            "is_frequent_buyer": bool(user.get("orderFrequencyPerMonth", 0) > 1),
        }

        # Remove None values
        return {k: v for k, v in labels.items() if v is not None}

    def _build_comprehensive_item_labels(
        self, product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build comprehensive Gorse item labels from all feature tables
        """
        labels = {
            # From ProductFeatures
            "view_count_30d": int(product.get("viewCount30d", 0)),
            "unique_viewers_30d": int(product.get("uniqueViewers30d", 0)),
            "cart_add_count_30d": int(product.get("cartAddCount30d", 0)),
            "purchase_count_30d": int(product.get("purchaseCount30d", 0)),
            "unique_purchasers_30d": int(product.get("uniquePurchasers30d", 0)),
            "view_to_cart_rate": (
                float(product.get("viewToCartRate", 0))
                if product.get("viewToCartRate")
                else 0
            ),
            "cart_to_purchase_rate": (
                float(product.get("cartToPurchaseRate", 0))
                if product.get("cartToPurchaseRate")
                else 0
            ),
            "overall_conversion_rate": (
                float(product.get("overallConversionRate", 0))
                if product.get("overallConversionRate")
                else 0
            ),
            "days_since_last_purchase": product.get("daysSinceLastPurchase"),
            "days_since_first_purchase": product.get("daysSinceFirstPurchase"),
            "avg_selling_price": (
                float(product.get("avgSellingPrice", 0))
                if product.get("avgSellingPrice")
                else 0
            ),
            "price_variance": (
                float(product.get("priceVariance", 0))
                if product.get("priceVariance")
                else 0
            ),
            "inventory_turnover": (
                float(product.get("inventoryTurnover", 0))
                if product.get("inventoryTurnover")
                else 0
            ),
            "stock_velocity": (
                float(product.get("stockVelocity", 0))
                if product.get("stockVelocity")
                else 0
            ),
            "price_tier": product.get("priceTier", "mid"),
            "popularity_score": float(product.get("popularityScore", 0)),
            "trending_score": float(product.get("trendingScore", 0)),
            "variant_complexity": (
                float(product.get("variantComplexity", 0))
                if product.get("variantComplexity")
                else 0
            ),
            "image_richness": (
                float(product.get("imageRichness", 0))
                if product.get("imageRichness")
                else 0
            ),
            "tag_diversity": (
                float(product.get("tagDiversity", 0))
                if product.get("tagDiversity")
                else 0
            ),
            # From ProductData
            "product_type": product.get("productType", "unknown"),
            "vendor": product.get("vendor", "unknown"),
            "in_stock": bool(product.get("totalInventory", 0) > 0),
            "has_discount": bool(
                product.get("compareAtPrice")
                and float(product.get("compareAtPrice", 0))
                > float(product.get("avgSellingPrice", 0))
            ),
            # From ProductCollectionFeatures
            "collection_count": int(product.get("collectionCount", 0)),
            "collection_quality_score": (
                float(product.get("collectionQualityScore", 0))
                if product.get("collectionQualityScore")
                else 0
            ),
            "cross_collection_score": (
                float(product.get("crossCollectionScore", 0))
                if product.get("crossCollectionScore")
                else 0
            ),
            "is_in_manual_collections": bool(
                product.get("isInManualCollections", False)
            ),
            "is_in_automated_collections": bool(
                product.get("isInAutomatedCollections", False)
            ),
            # From aggregated ProductPairFeatures
            "avg_lift_score": float(product.get("avg_lift_score", 0)),
            "frequently_bought_with_count": int(
                product.get("frequently_bought_with_count", 0)
            ),
            # From aggregated SearchProductFeatures
            "search_ctr": float(product.get("search_ctr", 0)),
            "search_conversion_rate": float(product.get("search_conversion_rate", 0)),
            # Computed flags
            "is_new": bool(
                product.get("days_since_first_purchase", 365) < 30
                if product.get("days_since_first_purchase")
                else False
            ),
            "is_bestseller": bool(product.get("purchase_count_30d", 0) > 10),
            "is_trending": bool(product.get("trending_score", 0) > 0.7),
            "needs_restock": bool(
                product.get("total_inventory", 1) < 10
                and product.get("stock_velocity", 0) > 0.5
            ),
        }

        # Add tags if available
        if product.get("tags"):
            tags = product["tags"]
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []
            if isinstance(tags, list) and tags:
                labels["tags"] = "|".join(tags[:5])  # Limit to 5 tags

        # Remove None values
        return {k: v for k, v in labels.items() if v is not None}

    async def _get_product_categories(
        self, product: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """
        Get categories from collections and CollectionFeatures
        """
        categories = []

        # Get from product collections
        collections = product.get("collections", "[]")
        if isinstance(collections, str):
            try:
                collections = json.loads(collections)
            except:
                collections = []

        for collection in collections:
            if isinstance(collection, dict):
                collection_id = collection.get("id")
                if collection_id:
                    categories.append(str(collection_id))
            elif isinstance(collection, str):
                categories.append(collection)

        # Also get high-performance collections from CollectionFeatures
        db = await self._get_database()
        query = """
            SELECT "collectionId" 
            FROM "CollectionFeatures" 
            WHERE "shopId" = $1 
                AND "performanceScore" > 0.5
            LIMIT 3
        """

        result = await db.query_raw(query, shop_id)
        top_collections = [dict(row) for row in result] if result else []
        for coll in top_collections:
            if coll["collectionId"] not in categories:
                categories.append(coll["collectionId"])

        return categories

    async def _sync_anonymous_users(self, shop_id: str):
        """
        Sync anonymous session users from SessionFeatures
        """
        db = await self._get_database()
        query = """
            SELECT 
                "sessionId",
                COUNT(*) as session_count,
                AVG("durationSeconds") as avg_duration,
                SUM("productViewCount") as total_views,
                SUM("cartAddCount") as total_cart_adds,
                SUM(CASE WHEN "checkoutCompleted" THEN 1 ELSE 0 END) as purchases,
                MAX("deviceType") as device_type,
                MAX("referrerDomain") as referrer
            FROM "SessionFeatures"
            WHERE "shopId" = $1 
                AND "customerId" IS NULL
                AND "endTime" > $2
            GROUP BY "sessionId"
        """

        since_time = now_utc() - timedelta(days=30)
        result = await db.query_raw(query, shop_id, since_time)
        sessions = [dict(row) for row in result] if result else []

        for session in sessions:
            user_id = f"session_{session['sessionId']}"

            labels = {
                "session_count": int(session["session_count"]),
                "avg_session_duration": float(session["avg_duration"] or 0),
                "product_view_count": int(session["total_views"] or 0),
                "cart_add_count": int(session["total_cart_adds"] or 0),
                "purchase_count": int(session["purchases"] or 0),
                "device_type": session["device_type"] or "unknown",
                "referrer": session["referrer"] or "direct",
                "is_anonymous": True,
                "customer_segment": "anonymous",
            }

            await self._upsert_gorse_user(user_id, shop_id, labels)

    async def _process_behavioral_events(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process behavioral events into feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "BehavioralEvents" 
            WHERE "shopId" = $1 
                AND "occurredAt" >= $2
            ORDER BY "occurredAt" ASC
        """

        result = await db.query_raw(query, shop_id, since_time)
        events = [dict(row) for row in result] if result else []

        feedback_list = []
        for event in events:
            feedback = self._convert_event_to_feedback(event)
            if feedback:
                feedback_list.extend(feedback)

        return feedback_list

    async def _process_orders(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process orders into purchase feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "OrderData" 
            WHERE "shopId" = $1 
                AND "orderDate" >= $2
        """

        result = await db.query_raw(query, shop_id, since_time)
        orders = [dict(row) for row in result] if result else []

        feedback_list = []
        for order in orders:
            feedback = self._convert_order_to_feedback(order)
            if feedback:
                feedback_list.extend(feedback)

        return feedback_list

    async def _process_interaction_features(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process InteractionFeatures for weighted feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "InteractionFeatures" 
            WHERE "shopId" = $1 
                AND "lastComputedAt" >= $2
                AND "interactionScore" > 0
        """

        result = await db.query_raw(query, shop_id, since_time)
        interactions = [dict(row) for row in result] if result else []

        feedback_list = []
        for interaction in interactions:
            # Create synthetic feedback based on interaction score
            if interaction["lastViewDate"]:
                feedback_list.append(
                    {
                        "feedback_type": "interaction",
                        "user_id": interaction["customerId"],
                        "item_id": interaction["productId"],
                        "timestamp": interaction["lastViewDate"],
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": float(interaction["interactionScore"]),
                                "affinity": float(interaction["affinityScore"] or 0),
                            }
                        ),
                    }
                )

        return feedback_list

    async def _process_session_feedback(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process SessionFeatures for session-based feedback
        """
        db = await self._get_database()
        query = """
            SELECT 
                sf.*,
                be."eventData"
            FROM "SessionFeatures" sf
            LEFT JOIN "BehavioralEvents" be 
                ON sf."sessionId" = be."sessionId" 
                AND be."eventType" = 'product_viewed'
            WHERE sf."shopId" = $1 
                AND sf."endTime" >= $2
                AND sf."productViewCount" > 0
        """

        result = await db.query_raw(query, shop_id, since_time)
        sessions = [dict(row) for row in result] if result else []

        feedback_list = []
        processed_sessions = set()

        for session in sessions:
            if session["sessionId"] in processed_sessions:
                continue
            processed_sessions.add(session["sessionId"])

            user_id = session["customerId"] or f"session_{session['sessionId']}"

            # Create session-level feedback if converted
            if session["checkoutCompleted"]:
                feedback_list.append(
                    {
                        "feedback_type": "session_conversion",
                        "user_id": user_id,
                        "item_id": "session_conversion",  # Special item for session conversions
                        "timestamp": session["endTime"],
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": 10.0,
                                "order_value": float(session["orderValue"] or 0),
                                "duration": session["durationSeconds"],
                            }
                        ),
                    }
                )

        return feedback_list

    # ... [Keep all the helper methods from the previous version] ...

    def _convert_event_to_feedback(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert behavioral event to feedback"""
        feedback_list = []

        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Determine user ID
        user_id = event.get("customerId")
        if not user_id:
            client_id = event_data.get("clientId")
            if client_id:
                user_id = f"session_{client_id}"
            else:
                return []

        # Map event types to feedback with weights
        feedback_mapping = {
            "product_viewed": ("view", 1.0),
            "product_added_to_cart": ("cart_add", 3.0),
            "collection_viewed": ("collection_view", 0.5),
            "search_submitted": ("search", 0.3),
            "checkout_started": ("checkout_start", 2.0),
            "checkout_completed": ("purchase", 7.0),
        }

        if event_type in feedback_mapping:
            feedback_type, weight = feedback_mapping[event_type]

            product_id = self._extract_product_id_from_event(event_type, event_data)

            if product_id:
                feedback_list.append(
                    {
                        "feedback_type": feedback_type,
                        "user_id": user_id,
                        "item_id": product_id,
                        "timestamp": event.get("occurredAt"),
                        "shop_id": event.get("shopId"),
                        "comment": json.dumps({"weight": weight}),
                    }
                )

        return feedback_list

    # Missing helper methods - Add placeholders for now, will implement based on Gorse schema
    async def _upsert_gorse_user(
        self, user_id: str, shop_id: str, labels: Dict[str, Any]
    ):
        """Upsert user to Gorse users table"""
        try:
            db = await self._get_database()

            await db.gorseusers.upsert(
                where={"userId": user_id},
                data={
                    "userId": user_id,
                    "shopId": shop_id,
                    "labels": labels,
                },
                create={
                    "userId": user_id,
                    "shopId": shop_id,
                    "labels": labels,
                },
            )

            logger.debug(f"Upserted Gorse user: {user_id} for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to upsert Gorse user {user_id}: {str(e)}")
            raise

    async def _upsert_gorse_item(
        self,
        item_id: str,
        shop_id: str,
        categories: List[str],
        labels: Dict[str, Any],
        is_hidden: bool = False,
    ):
        """Upsert item to Gorse items table"""
        try:
            db = await self._get_database()

            await db.gorseitems.upsert(
                where={"itemId": item_id},
                data={
                    "itemId": item_id,
                    "shopId": shop_id,
                    "categories": categories,
                    "labels": labels,
                    "isHidden": is_hidden,
                },
                create={
                    "itemId": item_id,
                    "shopId": shop_id,
                    "categories": categories,
                    "labels": labels,
                    "isHidden": is_hidden,
                },
            )

            logger.debug(f"Upserted Gorse item: {item_id} for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to upsert Gorse item {item_id}: {str(e)}")
            raise

    async def _insert_gorse_feedback(self, feedback: Dict[str, Any]):
        """Insert feedback to Gorse feedback table"""
        try:
            db = await self._get_database()

            # Convert feedback dict to Gorse schema format
            gorse_feedback_data = {
                "feedbackType": feedback["feedback_type"],
                "userId": feedback["user_id"],
                "itemId": feedback["item_id"],
                "timestamp": feedback["timestamp"],
                "shopId": feedback["shop_id"],
                "comment": feedback.get("comment"),
            }

            try:
                await db.gorsefeedback.create(data=gorse_feedback_data)
                logger.debug(
                    f"Inserted Gorse feedback: {feedback['feedback_type']} for user {feedback['user_id']} on item {feedback['item_id']}"
                )
            except Exception as create_error:
                # If it's a unique constraint violation, it's likely a duplicate, so we can skip it
                error_str = str(create_error).lower()
                if "unique constraint" in error_str or "duplicate" in error_str:
                    logger.debug(
                        f"Skipped duplicate Gorse feedback: {feedback['feedback_type']} for user {feedback['user_id']} on item {feedback['item_id']}"
                    )
                else:
                    # Re-raise if it's not a duplicate error
                    raise create_error

        except Exception as e:
            logger.error(f"Failed to insert Gorse feedback: {str(e)}")
            logger.error(f"Feedback data: {feedback}")
            raise

    def _should_hide_product(self, product: Dict[str, Any]) -> bool:
        """Determine if product should be hidden in Gorse"""
        # Hide products with low performance or out of stock
        total_inventory = product.get("totalInventory", 1)
        conversion_rate = product.get("overallConversionRate", 0)

        return not bool(total_inventory > 0) or (  # Out of stock
            conversion_rate is not None and float(conversion_rate) < 0.01
        )  # Very low conversion

    def _calculate_customer_segment(self, user: Dict[str, Any]) -> str:
        """Calculate customer segment based on user data"""
        lifetime_value = float(user.get("lifetimeValue", 0))
        order_frequency = float(user.get("orderFrequencyPerMonth", 0))

        if lifetime_value > 1000 and order_frequency > 2:
            return "vip"
        elif lifetime_value > 500 or order_frequency > 1:
            return "loyal"
        elif user.get("totalPurchases", 0) > 0:
            return "returning"
        else:
            return "new"

    def _extract_product_id_from_event(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> str:
        """Extract product ID from event data"""
        # Different event types may store product ID in different places
        product_id = event_data.get("productId") or event_data.get("product_id")
        if not product_id and "product" in event_data:
            product_id = event_data["product"].get("id")
        return product_id

    def _convert_order_to_feedback(self, order: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert order data to feedback"""
        feedback_list = []

        try:
            # Extract user ID (prefer customerId, fallback to email)
            user_id = order.get("customerId")
            if not user_id:
                user_id = order.get("customerEmail")

            if not user_id:
                logger.warning(f"No user ID found for order {order.get('orderId')}")
                return []

            # Extract line items (JSON array of products)
            line_items = order.get("lineItems", [])
            if isinstance(line_items, str):
                try:
                    line_items = json.loads(line_items)
                except:
                    line_items = []

            if not line_items:
                logger.debug(f"No line items found for order {order.get('orderId')}")
                return []

            # Get order metadata
            order_date = order.get("orderDate")
            shop_id = order.get("shopId")
            order_id = order.get("orderId")
            total_amount = float(order.get("totalAmount", 0))

            # Process each line item to create purchase feedback
            for item in line_items:
                try:
                    # Extract product ID from line item
                    product_id = None

                    # Try different possible structures for line items
                    if isinstance(item, dict):
                        # Check for variant -> product -> id structure
                        if "variant" in item and item["variant"]:
                            variant = item["variant"]
                            if isinstance(variant, dict) and "product" in variant:
                                product = variant["product"]
                                if isinstance(product, dict):
                                    product_id = product.get("id")

                        # Fallback: check for direct product_id or productId
                        if not product_id:
                            product_id = item.get("product_id") or item.get("productId")

                        # Another fallback: check for id field
                        if not product_id:
                            product_id = item.get("id")

                    if not product_id:
                        logger.debug(f"No product ID found in line item: {item}")
                        continue

                    # Extract quantity and price for weight calculation
                    quantity = int(item.get("quantity", 1))
                    line_total = 0

                    # Try to get line item value
                    if "variant" in item and item["variant"]:
                        variant = item["variant"]
                        if isinstance(variant, dict):
                            price = float(variant.get("price", 0))
                            line_total = price * quantity

                    # Calculate weight based on purchase value and quantity
                    base_weight = 7.0  # Base weight for purchase
                    quantity_bonus = min(
                        quantity * 0.5, 3.0
                    )  # Up to 3 extra points for quantity
                    value_bonus = min(
                        (line_total / 100) * 0.5, 2.0
                    )  # Up to 2 extra points for value
                    final_weight = base_weight + quantity_bonus + value_bonus

                    # Create feedback record
                    feedback = {
                        "feedback_type": "purchase",
                        "user_id": user_id,
                        "item_id": str(product_id),
                        "timestamp": order_date,
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": final_weight,
                                "order_id": order_id,
                                "quantity": quantity,
                                "line_total": line_total,
                                "total_order_value": total_amount,
                            }
                        ),
                    }

                    feedback_list.append(feedback)

                except Exception as item_error:
                    logger.error(f"Failed to process line item: {str(item_error)}")
                    logger.debug(f"Problematic line item: {item}")
                    continue

            if feedback_list:
                logger.debug(
                    f"Created {len(feedback_list)} purchase feedback records from order {order_id}"
                )

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to convert order to feedback: {str(e)}")
            logger.debug(f"Order data: {order}")
            return []

    def _deduplicate_feedback(
        self, feedback_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate feedback entries"""
        seen = set()
        unique_feedback = []

        for feedback in feedback_list:
            key = (
                feedback.get("user_id"),
                feedback.get("item_id"),
                feedback.get("feedback_type"),
                feedback.get("timestamp"),
            )
            if key not in seen:
                seen.add(key)
                unique_feedback.append(feedback)

        return unique_feedback


async def run_gorse_sync(shop_id: str):
    """
    Main entry point to run Gorse synchronization
    """
    pipeline = GorseSyncPipeline()
    await pipeline.sync_all(shop_id)
