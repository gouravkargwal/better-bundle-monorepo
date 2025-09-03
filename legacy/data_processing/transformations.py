"""
Feature transformation service: computes UserFeatures, ProductFeatures, InteractionFeatures.

Strategy:
- Pandas-first aggregations for fast in-memory processing
- Single database queries + bulk operations
- Fallback logic for shops without customer data (anonymous features)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import json

from prisma import Json
from app.core.config import settings
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)


async def _batch_create_many(db, model, data, batch_size=100):
    """Process data in batches to avoid memory issues with very large datasets."""
    if not data:
        return

    total_processed = 0
    for i in range(0, len(data), batch_size):
        batch = data[i : i + batch_size]
        try:
            await model.create_many(data=batch, skip_duplicates=True)
            total_processed += len(batch)
            logger.debug(f"Processed batch {i//batch_size + 1}: {len(batch)} records")
        except Exception as e:
            logger.warning(
                f"Batch insert failed, falling back to individual inserts: {e}"
            )
            # Fallback to individual inserts
            for item in batch:
                try:
                    await model.create(data=item)
                    total_processed += 1
                except Exception as individual_error:
                    logger.error(
                        f"Failed to insert individual record: {individual_error}"
                    )

    return total_processed


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _convert_datetime_to_iso(obj: Any) -> Any:
    """
    Recursively convert all datetime objects to ISO strings for JSON serialization.
    This function handles nested dictionaries, lists, and other data structures.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _convert_datetime_to_iso(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetime_to_iso(item) for item in obj]
    else:
        return obj


async def _check_customer_data_availability(shop_id: str) -> Dict[str, Any]:
    """Check if customer data is available for a shop."""
    db = await get_database()

    # Check if we have orders with customer IDs
    orders_with_customers = await db.orderdata.count(
        where={"shopId": shop_id, "customerId": {"not": None}}
    )

    # Check if we have customer data
    customer_count = await db.customerdata.count(where={"shopId": shop_id})

    # Check total orders
    total_orders = await db.orderdata.count(where={"shopId": shop_id})

    customer_data_ratio = (
        orders_with_customers / total_orders if total_orders > 0 else 0
    )

    return {
        "has_customer_data": customer_data_ratio
        > 0.1,  # At least 10% of orders have customer data
        "customer_data_ratio": customer_data_ratio,
        "orders_with_customers": orders_with_customers,
        "total_orders": total_orders,
        "customer_count": customer_count,
    }


async def _data_availability_status(shop_id: str) -> Dict[str, Any]:
    """Unified availability check across core datasets to drive adaptive computation."""
    db = await get_database()
    try:
        orders = await db.orderdata.count(where={"shopId": shop_id})
        products = await db.productdata.count(where={"shopId": shop_id})
        customers = await db.customerdata.count(where={"shopId": shop_id})
        collections = 0
        customer_events = 0
        try:
            collections = await db.collectiondata.count(where={"shopId": shop_id})
        except Exception:
            pass
        try:
            customer_events = await db.customereventdata.count(
                where={"shopId": shop_id}
            )
        except Exception:
            pass

        return {
            "orders": orders,
            "products": products,
            "customers": customers,
            "collections": collections,
            "customer_events": customer_events,
            "has_orders": orders > 0,
            "has_products": products > 0,
            "has_customers": customers > 0,
            "has_collections": collections > 0,
            "has_customer_events": customer_events > 0,
        }
    except Exception as e:
        logger.warning(f"Error checking data availability: {e}")
        return {
            "has_orders": False,
            "has_products": False,
            "has_customers": False,
            "has_collections": False,
            "has_customer_events": False,
        }


async def _compute_user_features(
    shop_id: str, customer_data_available: bool = True
) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    if not customer_data_available:
        logger.warning(
            f"Customer data not available for shop {shop_id}, skipping user features"
        )
        return {"user_features_ms": 0, "skipped": True, "reason": "no_customer_data"}

    try:
        # Fetch all order data using Prisma find_many + Pandas processing
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": {"not": None}},
        )

        if not orders:
            logger.warning(f"No orders found for shop {shop_id}")
            return {"user_features_ms": 0, "skipped": True, "reason": "no_orders"}

        # Convert to DataFrame
        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "customerId": order.customerId,
                    "totalAmount": order.totalAmount,
                    "orderDate": order.orderDate,
                }
            )

        orders_df = pd.DataFrame(orders_data)

        # Convert orderDate to datetime if it's not already
        orders_df["orderDate"] = pd.to_datetime(orders_df["orderDate"])

        # Group by customer and aggregate
        customer_features = (
            orders_df.groupby("customerId")
            .agg({"totalAmount": ["count", "sum"], "orderDate": "max"})
            .reset_index()
        )

        # Flatten column names
        customer_features.columns = [
            "customerId",
            "totalPurchases",
            "totalSpent",
            "lastOrderDate",
        ]

        # Calculate recency in days
        now = _now_utc()
        customer_features["recencyDays"] = (
            now - customer_features["lastOrderDate"]
        ).dt.days

        # Prepare bulk insert data
        bulk_data = []
        for _, row in customer_features.iterrows():
            bulk_data.append(
                {
                    "shopId": shop_id,
                    "customerId": row["customerId"],
                    "totalPurchases": int(row["totalPurchases"]),
                    "recencyDays": int(row["recencyDays"]),
                    "totalSpent": float(row["totalSpent"]),
                    "lastComputedAt": _now_utc(),
                }
            )

        # Bulk upsert using Prisma - optimized with bulk operations
        if bulk_data:
            try:
                await db.userfeatures.create_many(data=bulk_data, skip_duplicates=True)

            except Exception as e:
                logger.warning(
                    f"Bulk insert failed, falling back to individual upserts: {e}"
                )
                # Fallback to individual upserts if bulk insert fails
                for data in bulk_data:
                    await db.userfeatures.upsert(
                        where={
                            "shopId_customerId": {
                                "shopId": data["shopId"],
                                "customerId": data["customerId"],
                            }
                        },
                        data={
                            "create": data,
                            "update": {
                                "totalPurchases": data["totalPurchases"],
                                "recencyDays": data["recencyDays"],
                                "totalSpent": data["totalSpent"],
                                "lastComputedAt": data["lastComputedAt"],
                            },
                        },
                    )

    except Exception as e:
        logger.error(f"Error computing user features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000

    return {"user_features_ms": dur}


async def _compute_product_features(shop_id: str) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    try:
        # Fetch orders and products separately, then join in Python
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id},
        )

        products = await db.productdata.find_many(
            where={"shopId": shop_id},
        )

        if not products:
            return {"product_features_ms": 0, "skipped": True, "reason": "no_products"}

        if not orders:
            # Compute features that don't require orders (baseline popularity = 0)
            bulk_data = []
            for product in products:
                price = product.price or 0
                if price < settings.PRICE_TIER_LOW_MAX:
                    price_tier = "low"
                elif price >= settings.PRICE_TIER_HIGH_MIN:
                    price_tier = "high"
                else:
                    price_tier = "mid"

                bulk_data.append(
                    {
                        "shopId": shop_id,
                        "productId": product.productId,
                        "popularity": 0,
                        "priceTier": price_tier,
                        "category": (product.productType or ""),
                        "tags": Json(product.tags or {}),
                        "lastComputedAt": _now_utc(),
                    }
                )

            if bulk_data:
                try:
                    await db.productfeatures.create_many(
                        data=bulk_data, skip_duplicates=True
                    )
                except Exception as e:
                    logger.warning(
                        f"Bulk insert failed, falling back to individual upserts: {e}"
                    )
                    for data in bulk_data:
                        await db.productfeatures.upsert(
                            where={
                                "shopId_productId": {
                                    "shopId": data["shopId"],
                                    "productId": data["productId"],
                                }
                            },
                            data={
                                "create": data,
                                "update": {
                                    "popularity": data["popularity"],
                                    "priceTier": data["priceTier"],
                                    "category": data["category"],
                                    "tags": data["tags"],
                                    "lastComputedAt": data["lastComputedAt"],
                                },
                            },
                        )

            dur = (asyncio.get_event_loop().time() - start) * 1000
            return {"product_features_ms": dur, "skipped": False, "reason": "no_orders"}

        # Create product lookup dictionary and initialize ALL products
        product_lookup = {}
        product_stats = {}

        for product in products:
            product_stats[product.productId] = {
                "popularity": 0,
                "category": product.productType,
                "tags": product.tags,
                "price": product.price,
            }
            product_lookup[product.productId] = product

        # Process line items to extract order data and update popularity
        for order in orders:
            try:
                line_items = order.lineItems
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                for item in line_items:
                    product_id = item.get("productId", "").replace(
                        "gid://shopify/Product/", ""
                    )
                    quantity = item.get("quantity", 0)

                    if product_id in product_stats:
                        product_stats[product_id]["popularity"] += quantity

            except Exception as e:
                logger.warning(f"Error processing line items: {e}")
                continue

        # Prepare bulk insert data
        bulk_data = []
        for product_id, stats in product_stats.items():
            price = stats.get("price", 0)
            if price < settings.PRICE_TIER_LOW_MAX:
                price_tier = "low"
            elif price >= settings.PRICE_TIER_HIGH_MIN:
                price_tier = "high"
            else:
                price_tier = "mid"

            # Enhanced product features
            product = product_lookup.get(product_id, {})

            # Variant complexity
            variants = product.get("variants", [])
            variant_count = len(variants) if isinstance(variants, list) else 0
            variant_complexity = min(variant_count / 5.0, 1.0)  # Normalize to 0-1

            # Image richness
            images = product.get("images", [])
            image_count = len(images) if isinstance(images, list) else 0
            image_richness = min(image_count / 10.0, 1.0)  # Normalize to 0-1

            # Tag diversity
            tags = stats.get("tags", [])
            tag_diversity = min(len(tags) / 10.0, 1.0) if isinstance(tags, list) else 0

            # Metafield utilization
            metafields = product.get("metafields", [])
            metafield_count = len(metafields) if isinstance(metafields, list) else 0
            metafield_utilization = min(metafield_count / 5.0, 1.0)  # Normalize to 0-1

            # Category encoding (one-hot style)
            category = stats.get("category") or ""
            category_encoded = 1 if category else 0

            # Vendor diversity score
            vendor = stats.get("vendor") or ""
            vendor_score = 1 if vendor else 0

            bulk_data.append(
                {
                    "shopId": shop_id,
                    "productId": product_id,
                    "popularity": int(stats["popularity"]),
                    "priceTier": price_tier,
                    "category": category,
                    "tags": Json(stats.get("tags") or {}),
                    "variantComplexity": variant_complexity,
                    "imageRichness": image_richness,
                    "tagDiversity": tag_diversity,
                    "metafieldUtilization": metafield_utilization,
                    "categoryEncoded": category_encoded,
                    "vendorScore": vendor_score,
                    "lastComputedAt": _now_utc(),
                }
            )

        # Bulk upsert using Prisma - optimized with bulk operations
        if bulk_data:
            try:
                await db.productfeatures.create_many(
                    data=bulk_data, skip_duplicates=True
                )

            except Exception as e:
                logger.warning(
                    f"Bulk insert failed, falling back to individual upserts: {e}"
                )
                for data in bulk_data:
                    await db.productfeatures.upsert(
                        where={
                            "shopId_productId": {
                                "shopId": data["shopId"],
                                "productId": data["productId"],
                            }
                        },
                        data={
                            "create": data,
                            "update": {
                                "popularity": data["popularity"],
                                "priceTier": data["priceTier"],
                                "category": data["category"],
                                "tags": data["tags"],
                                "lastComputedAt": data["lastComputedAt"],
                            },
                        },
                    )

    except Exception as e:
        logger.error(f"Error computing product features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000
    return {"product_features_ms": dur}


async def _compute_interaction_features(
    shop_id: str, customer_data_available: bool = True
) -> Dict[str, Any]:
    db = await get_database()
    start = asyncio.get_event_loop().time()

    if not customer_data_available:
        logger.warning(
            f"Customer data not available for shop {shop_id}, skipping interaction features"
        )
        return {
            "interaction_features_ms": 0,
            "skipped": True,
            "reason": "no_customer_data",
        }

    try:
        # Fetch all order data using Prisma find_many + Pandas processing
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": {"not": None}},
        )

        if not orders:
            logger.warning(f"No orders found for shop {shop_id}")
            return {
                "interaction_features_ms": 0,
                "skipped": True,
                "reason": "no_orders",
            }

        # Convert to DataFrame
        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "customerId": order.customerId,
                    "orderDate": order.orderDate,
                    "lineItems": order.lineItems,
                }
            )

        orders_df = pd.DataFrame(orders_data)

        # Convert orderDate to datetime
        orders_df["orderDate"] = pd.to_datetime(orders_df["orderDate"])

        # Process line items to extract customer-product interactions
        interaction_stats = {}

        for _, row in orders_df.iterrows():
            try:
                line_items = row["lineItems"]
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                customer_id = row["customerId"]
                order_date = row["orderDate"]

                for item in line_items:
                    product_id = item.get("productId", "").replace(
                        "gid://shopify/Product/", ""
                    )
                    quantity = item.get("quantity", 0)

                    key = (customer_id, product_id)
                    if key not in interaction_stats:
                        interaction_stats[key] = {
                            "purchaseCount": 0,
                            "lastPurchaseDate": order_date,
                        }

                    interaction_stats[key]["purchaseCount"] += quantity
                    if order_date > interaction_stats[key]["lastPurchaseDate"]:
                        interaction_stats[key]["lastPurchaseDate"] = order_date

            except Exception as e:
                logger.warning(f"Error processing line items: {e}")
                continue

        # Calculate time-decayed weights
        now = _now_utc()
        for key, stats in interaction_stats.items():
            days_ago = (now - stats["lastPurchaseDate"]).days
            # Exponential decay: exp(-lambda * days)
            time_decay = np.exp(-settings.TIME_DECAY_LAMBDA * max(0, days_ago))
            stats["timeDecayedWeight"] = float(time_decay)

        # Prepare bulk insert data
        bulk_data = []
        for (customer_id, product_id), stats in interaction_stats.items():
            bulk_data.append(
                {
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "productId": product_id,
                    "purchaseCount": int(stats["purchaseCount"]),
                    "lastPurchaseDate": stats["lastPurchaseDate"],
                    "timeDecayedWeight": stats["timeDecayedWeight"],
                    "lastComputedAt": _now_utc(),
                }
            )

        # Bulk upsert using Prisma - optimized with bulk operations
        if bulk_data:
            try:
                await db.interactionfeatures.create_many(
                    data=bulk_data, skip_duplicates=True
                )

            except Exception as e:
                logger.warning(
                    f"Bulk insert failed, falling back to individual upserts: {e}"
                )
                # Fallback to individual upserts if bulk insert fails
                for data in bulk_data:
                    await db.interactionfeatures.upsert(
                        where={
                            "shopId_customerId_productId": {
                                "shopId": data["shopId"],
                                "customerId": data["customerId"],
                                "productId": data["productId"],
                            }
                        },
                        data={
                            "create": data,
                            "update": {
                                "purchaseCount": data["purchaseCount"],
                                "lastPurchaseDate": data["lastPurchaseDate"],
                                "timeDecayedWeight": data["timeDecayedWeight"],
                                "lastComputedAt": data["lastComputedAt"],
                            },
                        },
                    )

    except Exception as e:
        logger.error(f"Error computing interaction features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000

    return {"interaction_features_ms": dur}


async def _compute_customer_behavior_features(shop_id: str) -> Dict[str, Any]:
    """Compute customer behavior features from available data for Gorse ML training."""
    db = await get_database()
    start = asyncio.get_event_loop().time()

    try:
        # Check if we have customer events data
        customer_events = await db.customereventdata.find_many(
            where={"shopId": shop_id}
        )
        if not customer_events:
            return {
                "behavior_features_ms": 0,
                "skipped": True,
                "reason": "no_customer_events",
            }

        # Get customer data for additional context
        customers = await db.customerdata.find_many(where={"shopId": shop_id})
        customer_map = {c.customerId: c for c in customers}

        # Get orders for purchase patterns
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": {"not": None}}
        )

        if not orders:
            return {"behavior_features_ms": 0, "skipped": True, "reason": "no_orders"}

        # Process customer events to extract behavioral patterns
        customer_behavior = {}

        for event in customer_events:
            customer_id = event.customerId

            if customer_id not in customer_behavior:
                customer_behavior[customer_id] = {
                    "event_count": 0,
                    "event_types": set(),
                    "last_event": event.eventTimestamp,
                    "first_event": event.eventTimestamp,
                    "total_events": 0,
                }

            customer_behavior[customer_id]["event_count"] += 1
            customer_behavior[customer_id]["event_types"].add(event.eventType)

            if event.eventTimestamp > customer_behavior[customer_id]["last_event"]:
                customer_behavior[customer_id]["last_event"] = event.eventTimestamp
            if event.eventTimestamp < customer_behavior[customer_id]["first_event"]:
                customer_behavior[customer_id]["first_event"] = event.eventTimestamp

        # Process orders for purchase behavior
        customer_orders = {}
        for order in orders:
            customer_id = order.customerId
            if customer_id not in customer_orders:
                customer_orders[customer_id] = []
            customer_orders[customer_id].append(order)

        # Compute behavioral features
        behavioral_features = []
        now = _now_utc()

        for customer_id, behavior in customer_behavior.items():
            customer = customer_map.get(customer_id)
            if not customer:
                continue

            # Event-based features
            event_diversity = len(behavior["event_types"])
            event_frequency = behavior["event_count"]

            # Time-based features
            days_since_first_event = (now - behavior["first_event"]).days
            days_since_last_event = (now - behavior["last_event"]).days

            # Purchase behavior from orders
            customer_order_list = customer_orders.get(customer_id, [])
            purchase_frequency = len(customer_order_list)

            # Category preferences from orders
            category_preferences = {}
            for order in customer_order_list:
                try:
                    line_items = order.lineItems
                    if isinstance(line_items, str):
                        line_items = json.loads(line_items)

                    for item in line_items:
                        product_id = item.get("productId", "").replace(
                            "gid://shopify/Product/", ""
                        )
                        # Get product category from product data
                        # This is simplified - in production you'd join with product data
                        category = "unknown"  # Placeholder
                        if category not in category_preferences:
                            category_preferences[category] = 0
                        category_preferences[category] += item.get("quantity", 0)

                except Exception as e:
                    logger.warning(f"Error processing order line items: {e}")
                    continue

            # Top categories
            top_categories = sorted(
                category_preferences.items(), key=lambda x: x[1], reverse=True
            )[:3]
            top_category_names = [cat for cat, _ in top_categories]

            # Behavioral scoring
            engagement_score = min(event_frequency / 10.0, 1.0)  # Normalize to 0-1
            recency_score = max(
                0, 1 - (days_since_last_event / 365.0)
            )  # Decay over time
            diversity_score = min(event_diversity / 5.0, 1.0)  # Normalize to 0-1

            # Combined behavioral score
            behavioral_score = (
                engagement_score * 0.4 + recency_score * 0.4 + diversity_score * 0.2
            )

            behavioral_features.append(
                {
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "eventDiversity": event_diversity,
                    "eventFrequency": event_frequency,
                    "daysSinceFirstEvent": days_since_first_event,
                    "daysSinceLastEvent": days_since_last_event,
                    "purchaseFrequency": purchase_frequency,
                    "topCategories": Json(top_category_names),
                    "engagementScore": engagement_score,
                    "recencyScore": recency_score,
                    "diversityScore": diversity_score,
                    "behavioralScore": behavioral_score,
                    "lastComputedAt": _now_utc(),
                }
            )

        # Save behavioral features (we'll need to add this model to schema)
        if behavioral_features:
            try:
                # For now, we'll log the features
                # Later we can create a dedicated CustomerBehaviorFeatures model
                logger.info(
                    f"Computed behavioral features for {len(behavioral_features)} customers"
                )
            except Exception as e:
                logger.warning(f"Could not save behavioral features: {e}")

        # Compute behavioral analytics
        if behavioral_features:
            avg_engagement = sum(
                bf["engagementScore"] for bf in behavioral_features
            ) / len(behavioral_features)
            avg_recency = sum(bf["recencyScore"] for bf in behavioral_features) / len(
                behavioral_features
            )
            avg_diversity = sum(
                bf["diversityScore"] for bf in behavioral_features
            ) / len(behavioral_features)

            behavioral_analytics = {
                "total_customers_with_behavior": len(behavioral_features),
                "avg_engagement_score": avg_engagement,
                "avg_recency_score": avg_recency,
                "avg_diversity_score": avg_diversity,
                "high_engagement_customers": sum(
                    1 for bf in behavioral_features if bf["engagementScore"] > 0.7
                ),
                "active_customers": sum(
                    1 for bf in behavioral_features if bf["daysSinceLastEvent"] < 30
                ),
            }
        else:
            behavioral_analytics = {}

        logger.info(f"Customer behavior features computed: {behavioral_analytics}")

    except Exception as e:
        logger.error(
            f"Error computing customer behavior features for shop {shop_id}: {e}"
        )
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000
    return {"behavior_features_ms": dur, "behavioral_analytics": behavioral_analytics}


async def _compute_collection_features(shop_id: str) -> Dict[str, Any]:
    """Compute collection-based features for Gorse ML training."""
    db = await get_database()
    start = asyncio.get_event_loop().time()

    try:
        # Check if collections exist
        collections = await db.collectiondata.find_many(where={"shopId": shop_id})
        if not collections:
            return {
                "collection_features_ms": 0,
                "skipped": True,
                "reason": "no_collections",
            }

        # Get products to map collection relationships
        products = await db.productdata.find_many(where={"shopId": shop_id})
        product_collections = {}  # product_id -> list of collection_ids

        # Build product-collection mapping from raw collection data
        raw_collections = await db.rawcollection.find_many(where={"shopId": shop_id})

        for raw_collection in raw_collections:
            try:
                collection_data = raw_collection.payload
                collection_id = collection_data.get("id", "").replace(
                    "gid://shopify/Collection/", ""
                )

                # Extract products from this collection
                products_in_collection = collection_data.get("products", {}).get(
                    "edges", []
                )
                for product_edge in products_in_collection:
                    product_node = product_edge.get("node", {})
                    product_id = product_node.get("id", "").replace(
                        "gid://shopify/Product/", ""
                    )

                    if product_id not in product_collections:
                        product_collections[product_id] = []
                    product_collections[product_id].append(collection_id)

            except Exception as e:
                logger.warning(f"Error processing collection {raw_collection.id}: {e}")
                continue

        # Compute collection-level features
        collection_features = {}
        for collection in collections:
            collection_id = collection.collectionId

            # Count products in this collection
            product_count = sum(
                1
                for product_id, collections_list in product_collections.items()
                if collection_id in collections_list
            )

            # Determine if collection is automated
            is_automated = collection.isAutomated

            # Get collection performance from raw data
            collection_performance = 0
            try:
                raw_collection = next(
                    (
                        rc
                        for rc in raw_collections
                        if rc.payload.get("id", "").replace(
                            "gid://shopify/Collection/", ""
                        )
                        == collection_id
                    ),
                    None,
                )
                if raw_collection:
                    # Calculate performance based on products in collection
                    products_in_collection = [
                        pid
                        for pid, collections_list in product_collections.items()
                        if collection_id in collections_list
                    ]
                    # Get revenue from these products (simplified - could be enhanced with order data)
                    collection_performance = len(
                        products_in_collection
                    )  # Placeholder for now
            except Exception as e:
                logger.warning(f"Error computing collection performance: {e}")

            collection_features[collection_id] = {
                "product_count": product_count,
                "is_automated": is_automated,
                "performance_score": collection_performance,
                "seo_score": (
                    1 if collection.seoTitle or collection.seoDescription else 0
                ),
                "image_score": 1 if collection.imageUrl else 0,
            }

        # Compute product-collection features
        product_collection_features = []
        for product_id, collections_list in product_collections.items():
            if collections_list:  # Only process products that belong to collections
                # Collection diversity score
                collection_diversity = len(collections_list)

                # Collection quality score (manual collections often better curated)
                manual_collections = sum(
                    1
                    for cid in collections_list
                    if not collection_features.get(cid, {}).get("is_automated", True)
                )
                collection_quality_score = (
                    manual_collections / len(collections_list)
                    if collections_list
                    else 0
                )

                # Cross-collection bridge score (products in multiple collections are more versatile)
                cross_collection_score = min(
                    len(collections_list) / 5.0, 1.0
                )  # Normalize to 0-1

                product_collection_features.append(
                    {
                        "shopId": shop_id,
                        "productId": product_id,
                        "collectionCount": collection_diversity,
                        "collectionQualityScore": collection_quality_score,
                        "crossCollectionScore": cross_collection_score,
                        "isInManualCollections": manual_collections > 0,
                        "isInAutomatedCollections": len(collections_list)
                        - manual_collections
                        > 0,
                        "lastComputedAt": _now_utc(),
                    }
                )

        # Save product-collection features (we'll need to add this model to schema)
        if product_collection_features:
            try:
                # For now, we'll store this in product features as additional data
                # Later we can create a dedicated ProductCollectionFeatures model
                logger.info(
                    f"Computed collection features for {len(product_collection_features)} products"
                )
            except Exception as e:
                logger.warning(f"Could not save collection features: {e}")

        # Compute collection analytics
        total_collections = len(collections)
        manual_collections = sum(1 for c in collections if not c.isAutomated)
        automated_collections = total_collections - manual_collections

        collection_analytics = {
            "total_collections": total_collections,
            "manual_collections": manual_collections,
            "automated_collections": automated_collections,
            "avg_products_per_collection": (
                sum(cf["product_count"] for cf in collection_features.values())
                / total_collections
                if total_collections > 0
                else 0
            ),
            "collection_automation_ratio": (
                automated_collections / total_collections
                if total_collections > 0
                else 0
            ),
        }

        logger.info(f"Collection features computed: {collection_analytics}")

    except Exception as e:
        logger.error(f"Error computing collection features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000
    return {"collection_features_ms": dur, "collection_analytics": collection_analytics}


async def _compute_advanced_ml_features(shop_id: str) -> Dict[str, Any]:
    """Compute advanced ML features specifically optimized for Gorse ML training."""
    db = await get_database()
    start = asyncio.get_event_loop().time()

    try:
        # Check data availability
        orders = await db.orderdata.find_many(where={"shopId": shop_id})
        products = await db.productdata.find_many(where={"shopId": shop_id})
        customers = await db.customerdata.find_many(where={"shopId": shop_id})

        if not orders or not products:
            return {
                "advanced_ml_features_ms": 0,
                "skipped": True,
                "reason": "insufficient_data",
            }

        # 1. Time-based Patterns and Seasonal Trends
        time_patterns = _analyze_time_patterns(orders)

        # 2. Customer Segmentation Scores
        customer_segments = _compute_customer_segments(customers, orders)

        # 3. Product Similarity Matrix (simplified)
        product_similarities = _compute_product_similarities(products, orders)

        # 4. Category Performance Analysis
        category_performance = _analyze_category_performance(products, orders)

        # 5. Price Elasticity Indicators
        price_elasticity = _compute_price_elasticity(products, orders)

        # 6. Cross-Selling Opportunities
        cross_selling = _identify_cross_selling_opportunities(orders)

        # Combine all advanced features
        advanced_features = {
            "time_patterns": time_patterns,
            "customer_segments": customer_segments,
            "product_similarities": product_similarities,
            "category_performance": category_performance,
            "price_elasticity": price_elasticity,
            "cross_selling": cross_selling,
        }

        # Log summary
        logger.info(f"Advanced ML features computed for shop {shop_id}:")
        logger.info(f"  - Time patterns: {len(time_patterns)} patterns")
        logger.info(f"  - Customer segments: {len(customer_segments)} segments")
        logger.info(
            f"  - Product similarities: {len(product_similarities)} relationships"
        )
        logger.info(f"  - Category performance: {len(category_performance)} categories")

        # Store advanced features (we'll need to add this model to schema)
        try:
            # For now, we'll log the features
            # Later we can create a dedicated AdvancedMLFeatures model
            logger.info(f"Advanced ML features computed successfully")
        except Exception as e:
            logger.warning(f"Could not save advanced ML features: {e}")

    except Exception as e:
        logger.error(f"Error computing advanced ML features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000
    return {"advanced_ml_features_ms": dur, "features_summary": advanced_features}


def _analyze_time_patterns(orders: List[Any]) -> Dict[str, Any]:
    """Analyze time-based patterns in orders for seasonal trends."""
    try:
        # Convert to DataFrame for analysis
        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "orderDate": order.orderDate,
                    "totalAmount": order.totalAmount,
                    "month": order.orderDate.month,
                    "day_of_week": order.orderDate.weekday(),
                    "hour": order.orderDate.hour,
                }
            )

        if not orders_data:
            return {}

        df = pd.DataFrame(orders_data)

        # Monthly patterns
        monthly_revenue = df.groupby("month")["totalAmount"].sum()
        monthly_orders = df.groupby("month").size()

        # Day of week patterns
        dow_revenue = df.groupby("day_of_week")["totalAmount"].sum()
        dow_orders = df.groupby("day_of_week").size()

        # Peak hours
        hourly_revenue = df.groupby("hour")["totalAmount"].sum()

        return {
            "monthly_patterns": {
                "revenue": monthly_revenue.to_dict(),
                "orders": monthly_orders.to_dict(),
                "peak_month": (
                    monthly_revenue.idxmax() if not monthly_revenue.empty else None
                ),
                "low_month": (
                    monthly_revenue.idxmin() if not monthly_revenue.empty else None
                ),
            },
            "daily_patterns": {
                "revenue": dow_revenue.to_dict(),
                "orders": dow_orders.to_dict(),
                "peak_day": dow_revenue.idxmax() if not dow_revenue.empty else None,
            },
            "hourly_patterns": {
                "revenue": hourly_revenue.to_dict(),
                "peak_hour": (
                    hourly_revenue.idxmax() if not hourly_revenue.empty else None
                ),
            },
        }
    except Exception as e:
        logger.warning(f"Error analyzing time patterns: {e}")
        return {}


def _compute_customer_segments(
    customers: List[Any], orders: List[Any]
) -> Dict[str, Any]:
    """Compute customer segmentation scores for ML training."""
    try:
        # Group orders by customer
        customer_orders = {}
        for order in orders:
            if order.customerId:
                if order.customerId not in customer_orders:
                    customer_orders[order.customerId] = []
                customer_orders[order.customerId].append(order)

        # Compute customer segments
        segments = {
            "high_value": {"customers": [], "criteria": "total_spent > 1000"},
            "frequent_buyers": {"customers": [], "criteria": "order_count > 5"},
            "recent_buyers": {"customers": [], "criteria": "last_order < 30 days"},
            "lapsed_customers": {"customers": [], "criteria": "last_order > 90 days"},
        }

        now = _now_utc()

        for customer in customers:
            customer_id = customer.customerId
            customer_order_list = customer_orders.get(customer_id, [])

            total_spent = sum(order.totalAmount for order in customer_order_list)
            order_count = len(customer_order_list)
            last_order_date = max(
                (order.orderDate for order in customer_order_list), default=None
            )

            days_since_last_order = (
                (now - last_order_date).days if last_order_date else 999
            )

            # Segment assignment
            if total_spent > 1000:
                segments["high_value"]["customers"].append(customer_id)
            if order_count > 5:
                segments["frequent_buyers"]["customers"].append(customer_id)
            if days_since_last_order < 30:
                segments["recent_buyers"]["customers"].append(customer_id)
            if days_since_last_order > 90:
                segments["lapsed_customers"]["customers"].append(customer_id)

        # Add segment statistics
        for segment_name, segment_data in segments.items():
            segment_data["count"] = len(segment_data["customers"])
            segment_data["percentage"] = (
                (len(segment_data["customers"]) / len(customers)) * 100
                if customers
                else 0
            )

        return segments

    except Exception as e:
        logger.warning(f"Error computing customer segments: {e}")
        return {}


def _compute_product_similarities(
    products: List[Any], orders: List[Any]
) -> Dict[str, Any]:
    """Compute simplified product similarity matrix for ML training."""
    try:
        # Extract product categories and tags
        product_features = {}
        for product in products:
            product_features[product.productId] = {
                "category": product.productType or "",
                "vendor": product.vendor or "",
                "tags": product.tags or [],
                "price": product.price or 0,
            }

        # Simple similarity based on co-purchase patterns
        co_purchase_matrix = {}

        for order in orders:
            try:
                line_items = order.lineItems
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                product_ids = [
                    item.get("productId", "").replace("gid://shopify/Product/", "")
                    for item in line_items
                    if item.get("productId")
                ]

                # Build co-purchase relationships
                for i, pid1 in enumerate(product_ids):
                    for j, pid2 in enumerate(product_ids[i + 1 :], i + 1):
                        key = tuple(sorted([pid1, pid2]))
                        if key not in co_purchase_matrix:
                            co_purchase_matrix[key] = 0
                        co_purchase_matrix[key] += 1

            except Exception as e:
                logger.warning(f"Error processing order for similarity: {e}")
                continue

        # Convert to similarity scores
        similarities = []
        for (pid1, pid2), co_purchase_count in co_purchase_matrix.items():
            if co_purchase_count > 0:
                # Simple similarity score based on co-purchase frequency
                similarity_score = min(co_purchase_count / 5.0, 1.0)  # Normalize to 0-1

                similarities.append(
                    {
                        "product1": pid1,
                        "product2": pid2,
                        "similarity_score": similarity_score,
                        "co_purchase_count": co_purchase_count,
                    }
                )

        return {
            "total_similarities": len(similarities),
            "similarities": similarities[:100],  # Limit to top 100 for performance
        }

    except Exception as e:
        logger.warning(f"Error computing product similarities: {e}")
        return {}


def _analyze_category_performance(
    products: List[Any], orders: List[Any]
) -> Dict[str, Any]:
    """Analyze category performance for ML feature engineering."""
    try:
        # Build product category mapping
        product_categories = {p.productId: p.productType for p in products}

        # Analyze category performance from orders
        category_stats = {}

        for order in orders:
            try:
                line_items = order.lineItems
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                for item in line_items:
                    product_id = item.get("productId", "").replace(
                        "gid://shopify/Product/", ""
                    )
                    quantity = item.get("quantity", 0)
                    category = product_categories.get(product_id, "unknown")

                    if category not in category_stats:
                        category_stats[category] = {
                            "total_quantity": 0,
                            "total_revenue": 0,
                            "order_count": 0,
                            "products": set(),
                        }

                    category_stats[category]["total_quantity"] += quantity
                    category_stats[category]["total_revenue"] += quantity * (
                        item.get("price", 0) or 0
                    )
                    category_stats[category]["products"].add(product_id)

            except Exception as e:
                logger.warning(f"Error processing order for category analysis: {e}")
                continue

        # Convert to final format
        category_performance = {}
        for category, stats in category_stats.items():
            category_performance[category] = {
                "total_quantity": stats["total_quantity"],
                "total_revenue": stats["total_revenue"],
                "order_count": stats["order_count"],
                "unique_products": len(stats["products"]),
                "avg_revenue_per_product": (
                    stats["total_revenue"] / len(stats["products"])
                    if stats["products"]
                    else 0
                ),
            }

        return category_performance

    except Exception as e:
        logger.warning(f"Error analyzing category performance: {e}")
        return {}


def _compute_price_elasticity(products: List[Any], orders: List[Any]) -> Dict[str, Any]:
    """Compute price elasticity indicators for ML training."""
    try:
        # Group products by price ranges
        price_ranges = {
            "low": {"min": 0, "max": 25, "products": [], "orders": 0},
            "medium": {"min": 25, "max": 100, "products": [], "orders": 0},
            "high": {"min": 100, "max": float("inf"), "products": [], "orders": 0},
        }

        # Categorize products
        for product in products:
            price = product.price or 0
            for range_name, range_data in price_ranges.items():
                if range_data["min"] <= price < range_data["max"]:
                    range_data["products"].append(product.productId)
                    break

        # Count orders for each price range
        for order in orders:
            try:
                line_items = order.lineItems
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                for item in line_items:
                    product_id = item.get("productId", "").replace(
                        "gid://shopify/Product/", ""
                    )
                    # Find which price range this product belongs to
                    for range_name, range_data in price_ranges.items():
                        if product_id in range_data["products"]:
                            range_data["orders"] += 1
                            break

            except Exception as e:
                logger.warning(f"Error processing order for price elasticity: {e}")
                continue

        # Compute price elasticity indicators
        price_elasticity = {}
        for range_name, range_data in price_ranges.items():
            product_count = len(range_data["products"])
            order_count = range_data["orders"]

            price_elasticity[range_name] = {
                "product_count": product_count,
                "order_count": order_count,
                "order_per_product_ratio": (
                    order_count / product_count if product_count > 0 else 0
                ),
                "price_range": f"${range_data['min']}-${range_data['max'] if range_data['max'] != float('inf') else '∞'}",
            }

        return price_elasticity

    except Exception as e:
        logger.warning(f"Error computing price elasticity: {e}")
        return {}


def _identify_cross_selling_opportunities(orders: List[Any]) -> Dict[str, Any]:
    """Identify cross-selling opportunities for ML training."""
    try:
        # Analyze order patterns for cross-selling
        order_product_patterns = {}
        cross_selling_opportunities = []

        for order in orders:
            try:
                line_items = order.lineItems
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                product_ids = [
                    item.get("productId", "").replace("gid://shopify/Product/", "")
                    for item in line_items
                    if item.get("productId")
                ]

                if len(product_ids) > 1:  # Multi-product orders
                    order_key = tuple(sorted(product_ids))
                    if order_key not in order_product_patterns:
                        order_product_patterns[order_key] = 0
                    order_product_patterns[order_key] += 1

            except Exception as e:
                logger.warning(f"Error processing order for cross-selling: {e}")
                continue

        # Identify frequent product combinations
        for product_combination, frequency in order_product_patterns.items():
            if frequency >= 2:  # At least 2 orders with this combination
                cross_selling_opportunities.append(
                    {
                        "products": list(product_combination),
                        "frequency": frequency,
                        "confidence": min(
                            frequency / 10.0, 1.0
                        ),  # Normalize confidence
                    }
                )

        # Sort by frequency
        cross_selling_opportunities.sort(key=lambda x: x["frequency"], reverse=True)

        return {
            "total_opportunities": len(cross_selling_opportunities),
            "top_opportunities": cross_selling_opportunities[:20],  # Top 20
            "multi_product_orders": len(
                [o for o in order_product_patterns.values() if o > 1]
            ),
        }

    except Exception as e:
        logger.warning(f"Error identifying cross-selling opportunities: {e}")
        return {}


async def _compute_anonymous_features(shop_id: str) -> Dict[str, Any]:
    """Compute features that don't require customer data."""
    db = await get_database()
    start = asyncio.get_event_loop().time()

    try:
        # Fetch all order data using Prisma find_many + Pandas processing
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id},
        )

        if not orders:
            logger.warning(f"No orders found for shop {shop_id}")
            return {"anonymous_features_ms": 0, "skipped": True, "reason": "no_orders"}

        # Also fetch products for category mapping
        products = await db.productdata.find_many(where={"shopId": shop_id})
        product_category_map = {p.productId: (p.productType or "") for p in products}

        # Convert to DataFrame
        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "totalAmount": order.totalAmount,
                    "orderDate": order.orderDate,
                    "lineItems": order.lineItems,
                }
            )

        orders_df = pd.DataFrame(orders_data)

        # Calculate shop-level metrics
        total_orders = len(orders_df)
        total_revenue = orders_df["totalAmount"].sum()
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Process line items for top products and top categories
        product_quantities = {}
        category_quantities = {}

        for _, row in orders_df.iterrows():
            try:
                line_items = row["lineItems"]
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)

                for item in line_items:
                    product_id = item.get("productId", "").replace(
                        "gid://shopify/Product/", ""
                    )
                    quantity = item.get("quantity", 0)

                    if product_id not in product_quantities:
                        product_quantities[product_id] = 0
                    product_quantities[product_id] += quantity

                    category = product_category_map.get(product_id, "")
                    if category not in category_quantities:
                        category_quantities[category] = 0
                    category_quantities[category] += quantity

            except Exception as e:
                logger.warning(f"Error processing line items: {e}")
                continue

        # Get top 10 products by quantity
        top_products = sorted(
            product_quantities.items(), key=lambda x: x[1], reverse=True
        )[:10]
        top_products_json = [
            {"productId": pid, "totalQuantity": qty} for pid, qty in top_products
        ]

        # Get top categories
        top_categories = sorted(
            category_quantities.items(), key=lambda x: x[1], reverse=True
        )[:10]
        top_categories_json = [
            {"category": cat or "unknown", "totalQuantity": qty}
            for cat, qty in top_categories
        ]

        # Upsert shop analytics
        await db.shopanalytics.upsert(
            where={"shopId": shop_id},
            data={
                "create": {
                    "shopId": shop_id,
                    "totalOrders": int(total_orders),
                    "totalRevenue": float(total_revenue),
                    "avgOrderValue": float(avg_order_value),
                    "topProducts": top_products_json,
                    "topCategories": top_categories_json,
                    "lastComputedAt": _now_utc(),
                },
                "update": {
                    "totalOrders": int(total_orders),
                    "totalRevenue": float(total_revenue),
                    "avgOrderValue": float(avg_order_value),
                    "topProducts": top_products_json,
                    "topCategories": top_categories_json,
                    "lastComputedAt": _now_utc(),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error computing anonymous features for shop {shop_id}: {e}")
        raise

    dur = (asyncio.get_event_loop().time() - start) * 1000
    return {"anonymous_features_ms": dur}


async def _should_skip_computation(shop_id: str) -> Dict[str, Any]:
    """
    Check if computation for a shop should be skipped based on recent computation.
    Returns a dictionary indicating whether to skip and why.
    """
    db = await get_database()
    now = _now_utc()

    try:
        # Check when features were last computed using existing feature tables
        last_user_features = await db.userfeatures.find_first(
            where={"shopId": shop_id}, order={"lastComputedAt": "desc"}
        )

        last_product_features = await db.productfeatures.find_first(
            where={"shopId": shop_id}, order={"lastComputedAt": "desc"}
        )

        last_interaction_features = await db.interactionfeatures.find_first(
            where={"shopId": shop_id}, order={"lastComputedAt": "desc"}
        )

        # Check when data was last updated
        last_order = await db.orderdata.find_first(
            where={"shopId": shop_id}, order={"orderDate": "desc"}
        )

        last_product = await db.productdata.find_first(
            where={"shopId": shop_id}, order={"updatedAt": "desc"}
        )

        # Determine if we need to recompute
        skip_reason = None
        hours_since_computation = None  # Initialize variable

        if (
            not last_user_features
            or not last_product_features
            or not last_interaction_features
        ):
            skip_reason = "no_existing_features"
        elif last_order and last_user_features:
            # Check if orders are newer than features
            if last_order.orderDate > last_user_features.lastComputedAt:
                skip_reason = "new_orders_since_last_computation"
            elif (
                last_product
                and last_product.updatedAt > last_user_features.lastComputedAt
            ):
                skip_reason = "products_updated_since_last_computation"
            else:
                # Check if it's been more than 24 hours since last computation
                hours_since_computation = (
                    now - last_user_features.lastComputedAt
                ).total_seconds() / 3600
                if hours_since_computation < 24:
                    skip_reason = "recently_computed"

        should_skip = skip_reason in ["recently_computed"]

        return {
            "should_skip": should_skip,
            "reason": skip_reason,
            "last_computation": (
                last_user_features.lastComputedAt if last_user_features else None
            ),
            "last_order_date": last_order.orderDate if last_order else None,
            "last_product_update": last_product.updatedAt if last_product else None,
            "hours_since_computation": hours_since_computation,
        }

    except Exception as e:
        logger.warning(f"Error checking computation status: {e}")
        return {"should_skip": False, "reason": "error_checking_status"}


async def run_transformations_for_shop(
    shop_id: str, backfill_if_needed: bool = True
) -> Dict[str, Any]:
    """Run all feature transformations for a shop; return timing stats."""
    stats: Dict[str, Any] = {}

    try:
        # Check if we should skip computation (smart incremental logic)
        skip_check = await _should_skip_computation(shop_id)

        if skip_check["should_skip"]:

            # Convert datetime objects to ISO strings for JSON serialization
            last_computation = skip_check["last_computation"]
            if last_computation and hasattr(last_computation, "isoformat"):
                last_computation = last_computation.isoformat()

            hours_since_computation = skip_check["hours_since_computation"]
            if hours_since_computation and hasattr(
                hours_since_computation, "total_seconds"
            ):
                hours_since_computation = hours_since_computation.total_seconds() / 3600

            return {
                "success": True,
                "shop_id": shop_id,
                "skipped": True,
                "reason": skip_check["reason"],
                "last_computation": last_computation,
                "hours_since_computation": hours_since_computation,
                "message": "Features recently computed, no new data to process",
            }

        # Adaptive availability check
        availability = await _data_availability_status(shop_id)

        # Check data availability first
        data_status = await _check_customer_data_availability(shop_id)
        customer_data_available = (
            data_status["has_customer_data"] and availability["has_customers"]
        )

        if not availability["has_products"]:
            logger.warning(
                f"Shop {shop_id} has no products; only anonymous/shop-level features may be computed"
            )

        # Always compute product features if products exist
        if availability["has_products"]:
            p = await _compute_product_features(shop_id)
            stats.update(p)

        # Compute collection features if collections exist
        if availability["has_collections"]:
            c = await _compute_collection_features(shop_id)
            stats.update(c)

        # Compute customer-dependent features only if both orders and customers exist
        if availability["has_orders"] and customer_data_available:
            u = await _compute_user_features(shop_id, customer_data_available=True)
            i = await _compute_interaction_features(
                shop_id, customer_data_available=True
            )
            stats.update(u)
            stats.update(i)

            # Compute behavioral features if customer events exist
            if availability["has_customer_events"]:
                b = await _compute_customer_behavior_features(shop_id)
                stats.update(b)
        else:
            # Compute anonymous features as fallback if orders exist
            if availability["has_orders"]:
                a = await _compute_anonymous_features(shop_id)
                stats.update(a)
                stats["customer_features_skipped"] = True
                stats["fallback_features_computed"] = True
            else:
                stats["skipped_all"] = True
                stats["reason"] = "no_orders_no_customers"

        # Compute advanced ML features if we have sufficient data
        if availability["has_orders"] and availability["has_products"]:
            aml = await _compute_advanced_ml_features(shop_id)
            stats.update(aml)

        stats["data_availability"] = availability
        stats["customer_data_status"] = data_status
        stats["success"] = True
        stats["shop_id"] = shop_id

        # Convert datetime objects to ISO strings for JSON serialization
        if "last_computation" in stats and stats["last_computation"]:
            if hasattr(stats["last_computation"], "isoformat"):
                stats["last_computation"] = stats["last_computation"].isoformat()

        if "hours_since_computation" in stats and stats["hours_since_computation"]:
            if hasattr(stats["hours_since_computation"], "total_seconds"):
                stats["hours_since_computation"] = (
                    stats["hours_since_computation"].total_seconds() / 3600
                )

        return _convert_datetime_to_iso(stats)

    except Exception as e:
        logger.error(
            f"Transformations error | operation=run_transformations_for_shop | shop_id={shop_id} | error={str(e)}"
        )
        raise
