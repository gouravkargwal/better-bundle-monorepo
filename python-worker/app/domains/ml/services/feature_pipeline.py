"""
Feature pipeline orchestrator for coordinating feature generation and storage
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    ShopifyCustomerEvent,
)

from ..repositories.feature_repository import FeatureRepository, IFeatureRepository
from ..generators import (
    ProductFeatureGenerator,
    CustomerFeatureGenerator,
    OrderFeatureGenerator,
    CollectionFeatureGenerator,
    ShopFeatureGenerator,
)

logger = get_logger(__name__)


class IFeaturePipeline(ABC):
    """Interface for feature pipeline operations"""

    @abstractmethod
    async def run_feature_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 500
    ) -> Dict[str, Any]:
        """Run complete feature engineering pipeline for a shop"""
        pass

    @abstractmethod
    async def compute_and_save_product_features_batch(
        self, shop_id: str, products: List[ShopifyProduct], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save product features in batch"""
        pass

    @abstractmethod
    async def compute_and_save_customer_features_batch(
        self, shop_id: str, customers: List[ShopifyCustomer], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save customer features in batch"""
        pass

    @abstractmethod
    async def compute_and_save_collection_features_batch(
        self, shop_id: str, collections: List[ShopifyCollection], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save collection features in batch"""
        pass

    @abstractmethod
    async def compute_and_save_interaction_features_batch(
        self, shop_id: str, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute and save interaction features in batch"""
        pass


class FeaturePipeline(IFeaturePipeline):
    """Orchestrator for feature generation and storage pipeline"""

    def __init__(self, repository: Optional[IFeatureRepository] = None):
        self.repository = repository or FeatureRepository()

        # Initialize feature generators
        self.product_generator = ProductFeatureGenerator()
        self.customer_generator = CustomerFeatureGenerator()
        self.order_generator = OrderFeatureGenerator()
        self.collection_generator = CollectionFeatureGenerator()
        self.shop_generator = ShopFeatureGenerator()

    async def run_feature_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 500
    ) -> Dict[str, Any]:
        """Run complete feature engineering pipeline for a shop using batch processing"""
        try:
            logger.info(f"Starting feature pipeline for shop: {shop_id}")

            # Get all shop data
            shop_data = await self.repository.get_shop_data(shop_id)
            if not shop_data:
                return {"error": f"No data found for shop: {shop_id}"}

            shop = shop_data["shop"]
            products = shop_data["products"]
            orders = shop_data["orders"]
            customers = shop_data["customers"]
            collections = shop_data["collections"]
            events = shop_data["events"]

            results = {
                "shop_id": shop_id,
                "products": {"saved_count": 0, "total_products": 0},
                "customers": {"saved_count": 0, "total_customers": 0},
                "collections": {"saved_count": 0, "total_collections": 0},
                "interactions": {"saved_count": 0, "total_interactions": 0},
            }

            # Process products in batches
            if products:
                for i in range(0, len(products), batch_size):
                    batch = products[i : i + batch_size]
                    batch_result = await self.compute_and_save_product_features_batch(
                        shop_id, batch, shop
                    )
                    results["products"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    results["products"]["total_products"] += len(batch)

            # Process customers in batches
            if customers:
                for i in range(0, len(customers), batch_size):
                    batch = customers[i : i + batch_size]
                    batch_result = await self.compute_and_save_customer_features_batch(
                        shop_id, batch, shop
                    )
                    results["customers"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    results["customers"]["total_customers"] += len(batch)

            # Process collections in batches
            if collections:
                for i in range(0, len(collections), batch_size):
                    batch = collections[i : i + batch_size]
                    batch_result = (
                        await self.compute_and_save_collection_features_batch(
                            shop_id, batch, shop
                        )
                    )
                    results["collections"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    results["collections"]["total_collections"] += len(batch)

            # Process interactions
            if orders:
                interaction_result = (
                    await self.compute_and_save_interaction_features_batch(
                        shop_id, orders
                    )
                )
                results["interactions"] = interaction_result

            logger.info(f"Completed feature pipeline for shop: {shop_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to run feature pipeline for shop {shop_id}: {str(e)}")
            return {"error": str(e)}

    async def compute_and_save_product_features_batch(
        self, shop_id: str, products: List[ShopifyProduct], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save product features in batch to avoid N+1 writes"""
        try:
            # Prepare batch data
            batch_data = []
            for product in products:
                # Generate features using the product generator
                context = {"shop": shop}
                features = await self.product_generator.generate_features(
                    product, context
                )

                batch_data.append(
                    (
                        shop_id,
                        product.id,
                        features.get("total_orders", 0),
                        self.product_generator._get_price_tier(
                            features.get("avg_price", 0)
                        ),
                        product.product_type,
                        features.get("variant_count", 0)
                        / self.product_generator.normalization_divisors[
                            "variant_count"
                        ],
                        features.get("image_count", 0)
                        / self.product_generator.normalization_divisors["image_count"],
                        features.get("tag_diversity", 0)
                        / self.product_generator.normalization_divisors[
                            "tag_diversity"
                        ],
                        1 if product.product_type else 0,
                        1 if product.vendor else 0,
                        now_utc(),
                    )
                )

            if not batch_data:
                return {"saved_count": 0, "total_products": 0}

            # Use repository to save features
            saved_count = await self.repository.bulk_upsert_product_features(batch_data)
            return {"saved_count": saved_count, "total_products": len(products)}

        except Exception as e:
            logger.error(f"Failed to save product features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def compute_and_save_customer_features_batch(
        self, shop_id: str, customers: List[ShopifyCustomer], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save customer features in batch"""
        try:
            # Get customer IDs for batch queries
            customer_ids = [customer.id for customer in customers]

            # Fetch all orders and events for these customers
            orders_query = """
                SELECT * FROM "ShopifyOrder" 
                WHERE "shopId" = $1 AND "customerId" = ANY($2)
            """
            events_query = """
                SELECT * FROM "ShopifyCustomerEvent" 
                WHERE "shopId" = $1 AND "customerId" = ANY($2)
            """

            # Note: This would need to be implemented in the repository
            # For now, we'll use empty lists as the original code did
            orders = []
            events = []

            # Prepare batch data for UserFeatures and CustomerBehaviorFeatures
            user_features_batch = []
            behavior_features_batch = []

            for customer in customers:
                # Generate features using the customer generator
                context = {"shop": shop, "orders": orders, "events": events}
                features = await self.customer_generator.generate_features(
                    customer, context
                )

                # UserFeatures batch
                user_features_batch.append(
                    (
                        shop_id,
                        customer.id,
                        features.get("total_orders", 0),
                        features.get("total_spent", 0),
                        features.get("days_since_creation", 0),
                        features.get("average_order_value", 0),
                        None,  # preferred_category - simplified
                        now_utc(),
                    )
                )

                # CustomerBehaviorFeatures batch
                behavior_features_batch.append(
                    (
                        shop_id,
                        customer.id,
                        features.get("unique_event_types", 0),
                        features.get("event_count", 0),
                        features.get("days_since_creation", 0),
                        features.get("last_event_days", 0),
                        features.get("total_orders", 0),
                        features.get("engagement_score", 0),
                        features.get("engagement_score", 0),  # recency_score
                        features.get("unique_event_types", 0) / 10.0,  # diversity_score
                        features.get("engagement_score", 0),  # behavioral_score
                        now_utc(),
                    )
                )

            # Use repository to save features
            saved_count = await self.repository.bulk_upsert_customer_features(
                user_features_batch, behavior_features_batch
            )

            return {"saved_count": saved_count, "total_customers": len(customers)}

        except Exception as e:
            logger.error(f"Failed to save customer features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def compute_and_save_collection_features_batch(
        self, shop_id: str, collections: List[ShopifyCollection], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save collection features in batch"""
        try:
            # Prepare batch data
            batch_data = []
            for collection in collections:
                # Generate features using the collection generator
                context = {"shop": shop}
                features = await self.collection_generator.generate_features(
                    collection, context
                )

                batch_data.append(
                    (
                        shop_id,
                        collection.id,
                        features.get("products_count", 0),
                        1 if collection.is_automated else 0,
                        features.get("seo_score", 0),
                        features.get("seo_score", 0),  # seo_score
                        features.get("seo_score", 0),  # image_score
                        now_utc(),
                    )
                )

            if not batch_data:
                return {"saved_count": 0, "total_collections": 0}

            # Use repository to save features
            saved_count = await self.repository.bulk_upsert_collection_features(
                batch_data
            )
            return {"saved_count": saved_count, "total_collections": len(collections)}

        except Exception as e:
            logger.error(f"Failed to save collection features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def compute_and_save_interaction_features_batch(
        self, shop_id: str, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute and save interaction features in batch"""
        try:
            # Group interactions by customer-product pairs
            interactions = {}
            for order in orders:
                customer_id = order.customer_id
                if not customer_id:
                    continue

                for line_item in order.line_items:
                    product_id = line_item.product_id
                    if not product_id:
                        continue

                    key = f"{customer_id}_{product_id}"
                    if key not in interactions:
                        interactions[key] = {
                            "customerId": customer_id,
                            "productId": product_id,
                            "purchaseCount": 0,
                            "lastPurchaseDate": None,
                        }

                    interactions[key]["purchaseCount"] += line_item.quantity
                    interactions[key]["lastPurchaseDate"] = order.created_at

            # Prepare batch data
            batch_data = []
            for interaction in interactions.values():
                # Calculate time decayed weight
                days_since_purchase = (
                    (now_utc() - interaction["lastPurchaseDate"]).days
                    if interaction["lastPurchaseDate"]
                    else 0
                )
                time_decayed_weight = max(0, 1 - (days_since_purchase / 365))

                batch_data.append(
                    (
                        shop_id,
                        interaction["customerId"],
                        interaction["productId"],
                        interaction["purchaseCount"],
                        interaction["lastPurchaseDate"],
                        time_decayed_weight,
                        now_utc(),
                    )
                )

            if not batch_data:
                return {"saved_count": 0, "total_interactions": 0}

            # Use repository to save features
            saved_count = await self.repository.bulk_upsert_interaction_features(
                batch_data
            )
            return {"saved_count": saved_count, "total_interactions": len(interactions)}

        except Exception as e:
            logger.error(f"Failed to save interaction features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}
