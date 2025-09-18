#!/usr/bin/env python3
"""
Comprehensive data analysis script to check all main tables and calculations
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


async def analyze_raw_data_tables():
    """Analyze all raw data tables"""
    try:
        db = await get_database()
        shop_id = "cmfnmj5sn0000v3gaipwx948o"

        print("=" * 80)
        print("COMPREHENSIVE DATA ANALYSIS")
        print("=" * 80)

        # 1. UserInteraction Analysis
        print("\n1. USER INTERACTION ANALYSIS")
        print("-" * 40)

        total_interactions = await db.userinteraction.count(where={"shopId": shop_id})
        print(f"Total UserInteractions: {total_interactions}")

        # Group by interaction type
        interactions = await db.userinteraction.find_many(
            where={"shopId": shop_id}, take=1000
        )

        interaction_types = {}
        customer_interactions = {}
        product_interactions = {}

        for interaction in interactions:
            # Count by type
            event_type = interaction.interactionType
            if event_type not in interaction_types:
                interaction_types[event_type] = 0
            interaction_types[event_type] += 1

            # Count by customer
            customer_id = interaction.customerId
            if customer_id not in customer_interactions:
                customer_interactions[customer_id] = 0
            customer_interactions[customer_id] += 1

            # Extract product IDs for product_viewed events
            if event_type == "product_viewed":
                metadata = interaction.metadata
                if isinstance(metadata, dict):
                    data = metadata.get("data", {})
                    product_variant = data.get("productVariant", {})
                    product = product_variant.get("product", {})
                    product_id = product.get("id", "")
                    if product_id:
                        if product_id not in product_interactions:
                            product_interactions[product_id] = 0
                        product_interactions[product_id] += 1

        print(f"Interaction Types: {dict(sorted(interaction_types.items()))}")
        print(f"Unique Customers: {len(customer_interactions)}")
        print(f"Unique Products Viewed: {len(product_interactions)}")
        print(
            f"Top 5 Customers by Interactions: {sorted(customer_interactions.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )
        print(
            f"Top 5 Products by Views: {sorted(product_interactions.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )

        # 2. OrderData Analysis
        print("\n2. ORDER DATA ANALYSIS")
        print("-" * 40)

        total_orders = await db.orderdata.count(where={"shopId": shop_id})
        print(f"Total Orders: {total_orders}")

        orders = await db.orderdata.find_many(where={"shopId": shop_id}, take=100)

        order_customers = {}
        order_products = {}
        orders_with_line_items = 0
        orders_without_line_items = 0

        for order in orders:
            # Count by customer
            customer_id = order.customerId
            if customer_id not in order_customers:
                order_customers[customer_id] = 0
            order_customers[customer_id] += 1

            # Check line items
            line_items = order.lineItems
            if line_items is None:
                orders_without_line_items += 1
            else:
                orders_with_line_items += 1
                # Extract products from line items
                for item in line_items:
                    if isinstance(item, dict):
                        # Try different ways to extract product ID
                        product_id = None
                        if "productId" in item:
                            product_id = item["productId"]
                        elif "variant" in item and isinstance(item["variant"], dict):
                            product = item["variant"].get("product", {})
                            if isinstance(product, dict):
                                product_id = product.get("id")

                        if product_id:
                            if product_id not in order_products:
                                order_products[product_id] = 0
                            order_products[product_id] += 1

        print(f"Orders with Line Items: {orders_with_line_items}")
        print(f"Orders without Line Items: {orders_without_line_items}")
        print(f"Unique Order Customers: {len(order_customers)}")
        print(f"Unique Products in Orders: {len(order_products)}")
        print(
            f"Top 5 Customers by Orders: {sorted(order_customers.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )
        print(
            f"Top 5 Products by Orders: {sorted(order_products.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )

        # 3. ProductData Analysis
        print("\n3. PRODUCT DATA ANALYSIS")
        print("-" * 40)

        total_products = await db.productdata.count(where={"shopId": shop_id})
        print(f"Total Products: {total_products}")

        products = await db.productdata.find_many(where={"shopId": shop_id}, take=50)

        product_vendors = {}
        product_types = {}

        for product in products:
            vendor = product.vendor or "Unknown"
            if vendor not in product_vendors:
                product_vendors[vendor] = 0
            product_vendors[vendor] += 1

            product_type = product.productType or "Unknown"
            if product_type not in product_types:
                product_types[product_type] = 0
            product_types[product_type] += 1

        print(f"Unique Vendors: {len(product_vendors)}")
        print(
            f"Top 5 Vendors: {sorted(product_vendors.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )
        print(f"Product Types: {dict(sorted(product_types.items()))}")

        # 4. CustomerData Analysis
        print("\n4. CUSTOMER DATA ANALYSIS")
        print("-" * 40)

        total_customers = await db.customerdata.count(where={"shopId": shop_id})
        print(f"Total Customers: {total_customers}")

        customers = await db.customerdata.find_many(where={"shopId": shop_id}, take=50)

        customer_states = {}
        verified_customers = 0

        for customer in customers:
            state = customer.state or "Unknown"
            if state not in customer_states:
                customer_states[state] = 0
            customer_states[state] += 1

            if customer.verifiedEmail:
                verified_customers += 1

        print(f"Verified Customers: {verified_customers}")
        print(f"Customer States: {dict(sorted(customer_states.items()))}")

        # 5. CollectionData Analysis
        print("\n5. COLLECTION DATA ANALYSIS")
        print("-" * 40)

        total_collections = await db.collectiondata.count(where={"shopId": shop_id})
        print(f"Total Collections: {total_collections}")

        collections = await db.collectiondata.find_many(
            where={"shopId": shop_id}, take=50
        )

        automated_collections = 0
        manual_collections = 0
        total_products_in_collections = 0

        for collection in collections:
            if collection.isAutomated:
                automated_collections += 1
            else:
                manual_collections += 1

            total_products_in_collections += collection.productCount

        avg_products_per_collection = (
            total_products_in_collections / len(collections) if collections else 0
        )

        print(f"Automated Collections: {automated_collections}")
        print(f"Manual Collections: {manual_collections}")
        print(f"Total Products in Collections: {total_products_in_collections}")
        print(f"Average Products per Collection: {avg_products_per_collection:.1f}")

        return {
            "interactions": {
                "total": total_interactions,
                "types": interaction_types,
                "customers": len(customer_interactions),
                "products": len(product_interactions),
            },
            "orders": {
                "total": total_orders,
                "with_line_items": orders_with_line_items,
                "without_line_items": orders_without_line_items,
                "customers": len(order_customers),
                "products": len(order_products),
            },
            "products": {
                "total": total_products,
                "vendors": len(product_vendors),
                "types": len(product_types),
            },
            "customers": {
                "total": total_customers,
                "verified": verified_customers,
                "states": len(customer_states),
            },
            "collections": {
                "total": total_collections,
                "automated": automated_collections,
                "manual": manual_collections,
                "total_products": total_products_in_collections,
            },
        }

    except Exception as e:
        logger.error(f"Error in raw data analysis: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


async def analyze_feature_tables():
    """Analyze all feature tables"""
    try:
        db = await get_database()
        shop_id = "cmfnmj5sn0000v3gaipwx948o"

        print("\n6. FEATURE TABLES ANALYSIS")
        print("-" * 40)

        # InteractionFeatures
        interaction_features = await db.interactionfeatures.count(
            where={"shopId": shop_id}
        )
        print(f"InteractionFeatures: {interaction_features}")

        # Sample interaction features
        sample_interactions = await db.interactionfeatures.find_many(
            where={"shopId": shop_id}, take=10
        )

        total_views = 0
        total_cart_adds = 0
        total_purchases = 0

        for feature in sample_interactions:
            total_views += feature.viewCount
            total_cart_adds += feature.cartAddCount
            total_purchases += feature.purchaseCount

        print(f"Sample Interaction Features (first 10):")
        print(f"  Total Views: {total_views}")
        print(f"  Total Cart Adds: {total_cart_adds}")
        print(f"  Total Purchases: {total_purchases}")

        # CustomerBehaviorFeatures
        customer_behavior_features = await db.customerbehaviorfeatures.count(
            where={"shopId": shop_id}
        )
        print(f"CustomerBehaviorFeatures: {customer_behavior_features}")

        # ProductFeatures
        product_features = await db.productfeatures.count(where={"shopId": shop_id})
        print(f"ProductFeatures: {product_features}")

        # SessionFeatures
        session_features = await db.sessionfeatures.count(where={"shopId": shop_id})
        print(f"SessionFeatures: {session_features}")

        # CollectionFeatures
        collection_features = await db.collectionfeatures.count(
            where={"shopId": shop_id}
        )
        print(f"CollectionFeatures: {collection_features}")

        # ProductPairFeatures
        product_pair_features = await db.productpairfeatures.count(
            where={"shopId": shop_id}
        )
        print(f"ProductPairFeatures: {product_pair_features}")

        # SearchProductFeatures
        search_product_features = await db.searchproductfeatures.count(
            where={"shopId": shop_id}
        )
        print(f"SearchProductFeatures: {search_product_features}")

        return {
            "interaction_features": interaction_features,
            "customer_behavior_features": customer_behavior_features,
            "product_features": product_features,
            "session_features": session_features,
            "collection_features": collection_features,
            "product_pair_features": product_pair_features,
            "search_product_features": search_product_features,
        }

    except Exception as e:
        logger.error(f"Error in feature tables analysis: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


async def test_feature_calculations():
    """Test feature calculations with detailed logging"""
    try:
        from app.domains.ml.generators.interaction_feature_generator import (
            InteractionFeatureGenerator,
        )

        print("\n7. FEATURE CALCULATION TESTING")
        print("-" * 40)

        db = await get_database()
        shop_id = "cmfnmj5sn0000v3gaipwx948o"
        customer_id = "8619514265739"
        product_id = "7903465537675"  # Product with known issues

        print(f"Testing feature calculation for:")
        print(f"  Shop: {shop_id}")
        print(f"  Customer: {customer_id}")
        print(f"  Product: {product_id}")

        # Get raw data
        behavioral_events = await db.userinteraction.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

        print(f"\nRaw Data:")
        print(f"  Behavioral Events: {len(behavioral_events)}")
        print(f"  Orders: {len(orders)}")

        # Convert to dict format
        events_dict = []
        for event in behavioral_events:
            events_dict.append(
                {
                    "interactionType": event.interactionType,
                    "customerId": event.customerId,
                    "metadata": event.metadata,
                }
            )

        orders_dict = []
        for order in orders:
            orders_dict.append(
                {"customerId": order.customerId, "lineItems": order.lineItems}
            )

        # Test interaction feature generator
        generator = InteractionFeatureGenerator()
        context = {"behavioral_events": events_dict, "orders": orders_dict}

        print(f"\nTesting Interaction Feature Generator:")
        try:
            features = await generator.generate_features(
                shop_id, customer_id, product_id, context
            )

            print(f"  ✅ Generated successfully")
            print(f"  View Count: {features.get('viewCount', 0)}")
            print(f"  Cart Add Count: {features.get('cartAddCount', 0)}")
            print(f"  Purchase Count: {features.get('purchaseCount', 0)}")
            print(f"  Interaction Score: {features.get('interactionScore', 0)}")
            print(f"  Affinity Score: {features.get('affinityScore', 0)}")

        except Exception as e:
            print(f"  ❌ Error in feature generation: {str(e)}")
            import traceback

            traceback.print_exc()

        return True

    except Exception as e:
        logger.error(f"Error in feature calculation testing: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main analysis function"""
    try:
        print(f"Starting comprehensive data analysis at {datetime.now()}")

        # Analyze raw data tables
        raw_data_analysis = await analyze_raw_data_tables()

        # Analyze feature tables
        feature_analysis = await analyze_feature_tables()

        # Test feature calculations
        calculation_test = await test_feature_calculations()

        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)

        if raw_data_analysis:
            print(f"Raw Data: ✅ {raw_data_analysis}")
        else:
            print(f"Raw Data: ❌ Failed")

        if feature_analysis:
            print(f"Feature Tables: ✅ {feature_analysis}")
        else:
            print(f"Feature Tables: ❌ Failed")

        if calculation_test:
            print(f"Feature Calculations: ✅ Working")
        else:
            print(f"Feature Calculations: ❌ Failed")

        print(f"\nAnalysis completed at {datetime.now()}")

    except Exception as e:
        logger.error(f"Error in main analysis: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
