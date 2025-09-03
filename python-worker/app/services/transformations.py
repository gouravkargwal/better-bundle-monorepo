"""
Feature transformation service: computes UserFeatures, ProductFeatures, InteractionFeatures.

Strategy:
- Pandas-first aggregations for fast in-memory processing
- Single database queries + bulk operations
- Fallback logic for shops without customer data (anonymous features)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
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

        if not orders:
            return {"product_features_ms": 0, "skipped": True, "reason": "no_orders"}

        # Create product lookup dictionary and initialize ALL products
        product_lookup = {}
        product_stats = {}

        # Initialize ALL products first (not just ordered ones)
        for product in products:
            product_stats[product.productId] = {
                "popularity": 0,  # Will be 0 if never ordered
                "category": product.category,
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

                    # Update popularity for products that were ordered
                    if product_id in product_stats:
                        product_stats[product_id]["popularity"] += quantity

            except Exception as e:
                logger.warning(f"Error processing line items: {e}")
                continue

        # Prepare bulk insert data
        bulk_data = []
        for product_id, stats in product_stats.items():
            # Determine price tier
            price = stats.get("price", 0)
            if price < settings.PRICE_TIER_LOW_MAX:
                price_tier = "low"
            elif price >= settings.PRICE_TIER_HIGH_MIN:
                price_tier = "high"
            else:
                price_tier = "mid"

            bulk_data.append(
                {
                    "shopId": shop_id,
                    "productId": product_id,
                    "popularity": int(stats["popularity"]),
                    "priceTier": price_tier,
                    "category": stats.get("category") or "",
                    "tags": Json(stats.get("tags") or {}),
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
                # Fallback to individual upserts if bulk insert fails
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

        # Process line items for top products
        product_quantities = {}

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
                    "topCategories": [],  # TODO: Add category analysis
                    "lastComputedAt": _now_utc(),
                },
                "update": {
                    "totalOrders": int(total_orders),
                    "totalRevenue": float(total_revenue),
                    "avgOrderValue": float(avg_order_value),
                    "topProducts": top_products_json,
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

        # Check data availability first
        data_status = await _check_customer_data_availability(shop_id)
        customer_data_available = data_status["has_customer_data"]

        if not customer_data_available:
            logger.warning(
                f"Shop {shop_id} has limited customer data ({data_status['customer_data_ratio']:.1%}), using fallback features"
            )

        # Always compute product features (works without customer data)
        p = await _compute_product_features(shop_id)
        stats.update(p)

        # Compute customer-dependent features only if data is available
        if customer_data_available:
            u = await _compute_user_features(shop_id, customer_data_available=True)
            i = await _compute_interaction_features(
                shop_id, customer_data_available=True
            )
            stats.update(u)
            stats.update(i)
        else:
            # Compute anonymous features as fallback
            a = await _compute_anonymous_features(shop_id)
            stats.update(a)
            stats["customer_features_skipped"] = True
            stats["fallback_features_computed"] = True

        stats["data_availability"] = data_status
        stats["computation_info"] = skip_check
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
