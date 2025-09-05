"""
Feature pipeline orchestrator for coordinating feature generation and storage
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    BehavioralEvent,
)

from ..repositories.feature_repository import FeatureRepository, IFeatureRepository
from ..generators import (
    ProductFeatureGenerator,
    CustomerFeatureGenerator,
    OrderFeatureGenerator,
    CollectionFeatureGenerator,
    ShopFeatureGenerator,
)
from ..generators.interaction_feature_generator import InteractionFeatureGenerator
from ..generators.session_feature_generator import SessionFeatureGenerator

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
        self, shop_id: str, products: List[ShopifyProduct], shop_id_param: str
    ) -> Dict[str, Any]:
        """Compute and save product features in batch"""
        pass

    @abstractmethod
    async def compute_and_save_customer_features_batch(
        self,
        shop_id: str,
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
        events: List[BehavioralEvent],
    ) -> Dict[str, Any]:
        """Compute and save customer features in batch with actual orders and events"""
        pass

    @abstractmethod
    async def compute_and_save_collection_features_batch(
        self, shop_id: str, collections: List[ShopifyCollection], shop_id_param: str
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

        # Initialize enhanced feature generators
        self.interaction_generator = InteractionFeatureGenerator()
        self.session_generator = SessionFeatureGenerator()

    async def run_feature_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 500, incremental: bool = True
    ) -> Dict[str, Any]:
        """Run complete feature engineering pipeline for a shop using batch processing"""
        try:
            logger.info(
                f"Starting feature pipeline for shop: {shop_id} (incremental: {incremental})"
            )

            if incremental:
                return await self._run_incremental_pipeline(shop_id, batch_size)
            else:
                return await self._run_full_pipeline(shop_id, batch_size)

        except Exception as e:
            logger.error(f"Failed to run feature pipeline for shop {shop_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

    async def _run_incremental_pipeline(
        self, shop_id: str, batch_size: int
    ) -> Dict[str, Any]:
        """Run incremental feature pipeline processing only changed data"""
        try:
            # Get last computation timestamp
            last_computation_time = (
                await self.repository.get_shop_last_computation_time(shop_id)
            )
            current_time = now_utc()

            logger.info(
                f"Processing incremental updates since: {last_computation_time}"
            )

            results = {
                "shop_id": shop_id,
                "products": {"saved_count": 0, "total_products": 0},
                "customers": {"saved_count": 0, "total_customers": 0},
                "collections": {"saved_count": 0, "total_collections": 0},
                "interactions": {"saved_count": 0, "total_interactions": 0},
                "batch_size": batch_size,
                "incremental": True,
                "since_timestamp": last_computation_time,
            }

            # Step 1: Get directly changed entities (updatedAt > lastComputationTime)
            directly_changed_products = await self._get_directly_changed_products(
                shop_id, last_computation_time
            )
            directly_changed_customers = await self._get_directly_changed_customers(
                shop_id, last_computation_time
            )
            directly_changed_collections = await self._get_directly_changed_collections(
                shop_id, last_computation_time
            )

            # Step 2: Get indirectly affected entities from new orders
            affected_entity_ids = (
                await self.repository.get_affected_entity_ids_from_orders(
                    shop_id, last_computation_time
                )
            )
            indirectly_affected_products = await self.repository.get_products_by_ids(
                shop_id, affected_entity_ids["product_ids"]
            )
            indirectly_affected_customers = await self.repository.get_customers_by_ids(
                shop_id, affected_entity_ids["customer_ids"]
            )

            # Step 3: Consolidate and deduplicate entities
            all_products_to_process = self._consolidate_entities(
                directly_changed_products, indirectly_affected_products
            )
            all_customers_to_process = self._consolidate_entities(
                directly_changed_customers, indirectly_affected_customers
            )

            # Step 4: Process consolidated entities in batches
            await self._process_products_batch(
                shop_id, all_products_to_process, batch_size, results
            )
            await self._process_customers_batch(
                shop_id, all_customers_to_process, batch_size, results
            )
            await self._process_collections_batch(
                shop_id, directly_changed_collections, batch_size, results
            )

            # Step 5: Process new orders for interactions in batches
            await self._process_orders_incremental(
                shop_id, last_computation_time, batch_size, results
            )

            # Update last computation timestamp
            await self.repository.update_shop_last_computation_time(
                shop_id, current_time
            )

            logger.info(f"Completed incremental feature pipeline for shop: {shop_id}")
            return {
                "success": True,
                "results": results,
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Failed to run incremental pipeline for shop {shop_id}: {str(e)}"
            )
            return {
                "success": False,
                "error": str(e),
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

    async def _run_full_pipeline(self, shop_id: str, batch_size: int) -> Dict[str, Any]:
        """Run full feature pipeline processing all data"""
        try:
            # Get entity counts for pagination
            product_count = await self.repository.get_entity_count(
                shop_id, "ShopifyProduct"
            )
            order_count = await self.repository.get_entity_count(
                shop_id, "ShopifyOrder"
            )
            customer_count = await self.repository.get_entity_count(
                shop_id, "ShopifyCustomer"
            )
            collection_count = await self.repository.get_entity_count(
                shop_id, "ShopifyCollection"
            )
            event_count = await self.repository.get_entity_count(
                shop_id, "ShopifyEvent"
            )

            if product_count == 0 and order_count == 0 and customer_count == 0:
                return {"error": f"No data found for shop: {shop_id}"}

            results = {
                "shop_id": shop_id,
                "products": {"saved_count": 0, "total_products": product_count},
                "customers": {"saved_count": 0, "total_customers": customer_count},
                "collections": {
                    "saved_count": 0,
                    "total_collections": collection_count,
                },
                "interactions": {"saved_count": 0, "total_interactions": 0},
                "batch_size": batch_size,
            }

            # Process products in batches
            if product_count > 0:
                offset = 0
                while offset < product_count:
                    products_batch = await self.repository.get_products_batch(
                        shop_id, batch_size, offset
                    )
                    if not products_batch:
                        break

                    # Convert raw data to Pydantic models
                    products_models = [
                        ShopifyProduct(**product) for product in products_batch
                    ]
                    batch_result = await self.compute_and_save_product_features_batch(
                        shop_id, products_models, shop_id
                    )
                    results["products"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    offset += batch_size

            # Process customers in batches
            if customer_count > 0:
                offset = 0
                while offset < customer_count:
                    customers_batch = await self.repository.get_customers_batch(
                        shop_id, batch_size, offset
                    )
                    if not customers_batch:
                        break

                    # For full pipeline, we need to fetch orders and events for customers
                    customer_ids = [
                        customer.get("id")
                        for customer in customers_batch
                        if customer.get("id")
                    ]
                    orders_raw = await self.repository.get_orders_for_customer_ids(
                        shop_id, customer_ids
                    )
                    events_raw = await self.repository.get_events_for_customer_ids(
                        shop_id, customer_ids
                    )

                    # Convert raw data to Pydantic models
                    customers_models = [
                        ShopifyCustomer(**customer) for customer in customers_batch
                    ]
                    orders_models = [ShopifyOrder(**order) for order in orders_raw]
                    events_models = [BehavioralEvent(**event) for event in events_raw]

                    batch_result = await self.compute_and_save_customer_features_batch(
                        shop_id, customers_models, orders_models, events_models
                    )
                    results["customers"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    offset += batch_size

            # Process collections in batches
            if collection_count > 0:
                offset = 0
                while offset < collection_count:
                    collections_batch = await self.repository.get_collections_batch(
                        shop_id, batch_size, offset
                    )
                    if not collections_batch:
                        break

                    # Convert raw data to Pydantic models
                    collections_models = [
                        ShopifyCollection(**collection)
                        for collection in collections_batch
                    ]
                    batch_result = (
                        await self.compute_and_save_collection_features_batch(
                            shop_id, collections_models, shop_id
                        )
                    )
                    results["collections"]["saved_count"] += batch_result.get(
                        "saved_count", 0
                    )
                    offset += batch_size

            # Process interactions (using orders data)
            if order_count > 0:
                # Get all orders for interaction features (this is typically smaller than other entities)
                orders = await self.repository.get_orders_for_shop(shop_id)
                if orders:
                    interaction_result = (
                        await self.compute_and_save_interaction_features_batch(
                            shop_id, orders
                        )
                    )
                    results["interactions"] = interaction_result

            logger.info(f"Completed feature pipeline for shop: {shop_id}")
            return {
                "success": True,
                "results": results,
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to run feature pipeline for shop {shop_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

    async def compute_and_save_product_features_batch(
        self, shop_id: str, products: List[Dict[str, Any]], shop_id_param: str
    ) -> Dict[str, Any]:
        """Compute and save product features in batch to avoid N+1 writes"""
        try:
            # Prepare batch data
            batch_data = []
            for product in products:
                # Generate features using the product generator
                context = {"shop_id": shop_id_param}
                features = await self.product_generator.generate_features(
                    product, context
                )

                batch_data.append(
                    (
                        shop_id,
                        product.get("id"),
                        features.get("total_orders", 0),
                        self.product_generator._get_price_tier(
                            features.get("avg_price", 0)
                        ),
                        product.get("product_type"),
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
        self,
        shop_id: str,
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
        events: List[BehavioralEvent],
    ) -> Dict[str, Any]:
        """Compute and save customer features in batch with actual orders and events"""
        try:
            # Group orders and events by customer ID for efficient lookup
            orders_by_customer = {}
            events_by_customer = {}

            for order in orders:
                customer_id = order.customerId
                if customer_id:
                    if customer_id not in orders_by_customer:
                        orders_by_customer[customer_id] = []
                    orders_by_customer[customer_id].append(order)

            for event in events:
                customer_id = event.customerId
                if customer_id:
                    if customer_id not in events_by_customer:
                        events_by_customer[customer_id] = []
                    events_by_customer[customer_id].append(event)

            # Prepare batch data for UserFeatures and CustomerBehaviorFeatures
            user_features_batch = []
            behavior_features_batch = []

            for customer in customers:
                customer_id = customer.id
                customer_orders = orders_by_customer.get(customer_id, [])
                customer_events = events_by_customer.get(customer_id, [])

                # Generate features using the customer generator with actual data
                context = {
                    "shop_id": shop_id,
                    "orders": customer_orders,
                    "events": customer_events,
                }
                features = await self.customer_generator.generate_features(
                    customer, context
                )

                # Generate enhanced session features
                session_features = await self.session_generator.generate_features(
                    customer, context
                )
                features.update(session_features)

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

    async def _process_orders_incremental(
        self,
        shop_id: str,
        since_timestamp: str,
        batch_size: int,
        results: Dict[str, Any],
    ) -> None:
        """Process new orders for interaction features since last computation"""
        try:
            all_orders = []
            offset = 0

            # Collect all new orders in batches
            while True:
                orders_batch = await self.repository.get_orders_batch_since(
                    shop_id, since_timestamp, batch_size, offset
                )
                if not orders_batch:
                    break
                all_orders.extend(orders_batch)
                offset += batch_size

            if all_orders:
                # Process all orders for interactions
                interaction_result = (
                    await self.compute_and_save_interaction_features_batch(
                        shop_id, all_orders
                    )
                )
                results["interactions"] = interaction_result
                logger.info(f"Processed {len(all_orders)} new orders for interactions")
        except Exception as e:
            logger.error(f"Failed to process orders incrementally: {str(e)}")

    async def _get_directly_changed_products(
        self, shop_id: str, since_timestamp: str
    ) -> List[Dict[str, Any]]:
        """Get all products that were directly updated since timestamp"""
        try:
            all_products = []
            offset = 0
            batch_size = 1000  # Larger batch for fetching all changed products

            while True:
                products_batch = await self.repository.get_products_batch_since(
                    shop_id, since_timestamp, batch_size, offset
                )
                if not products_batch:
                    break
                all_products.extend(products_batch)
                offset += batch_size

            logger.info(f"Found {len(all_products)} directly changed products")
            return all_products
        except Exception as e:
            logger.error(f"Failed to get directly changed products: {str(e)}")
            return []

    async def _get_directly_changed_customers(
        self, shop_id: str, since_timestamp: str
    ) -> List[Dict[str, Any]]:
        """Get all customers that were directly updated since timestamp"""
        try:
            all_customers = []
            offset = 0
            batch_size = 1000  # Larger batch for fetching all changed customers

            while True:
                customers_batch = await self.repository.get_customers_batch_since(
                    shop_id, since_timestamp, batch_size, offset
                )
                if not customers_batch:
                    break
                all_customers.extend(customers_batch)
                offset += batch_size

            logger.info(f"Found {len(all_customers)} directly changed customers")
            return all_customers
        except Exception as e:
            logger.error(f"Failed to get directly changed customers: {str(e)}")
            return []

    async def _get_directly_changed_collections(
        self, shop_id: str, since_timestamp: str
    ) -> List[Dict[str, Any]]:
        """Get all collections that were directly updated since timestamp"""
        try:
            all_collections = []
            offset = 0
            batch_size = 1000  # Larger batch for fetching all changed collections

            while True:
                collections_batch = await self.repository.get_collections_batch_since(
                    shop_id, since_timestamp, batch_size, offset
                )
                if not collections_batch:
                    break
                all_collections.extend(collections_batch)
                offset += batch_size

            logger.info(f"Found {len(all_collections)} directly changed collections")
            return all_collections
        except Exception as e:
            logger.error(f"Failed to get directly changed collections: {str(e)}")
            return []

    def _consolidate_entities(
        self,
        direct_entities: List[Dict[str, Any]],
        indirect_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Consolidate and deduplicate entities from direct and indirect changes"""
        try:
            # Create a dictionary to deduplicate by ID
            consolidated = {}

            # Add direct entities first
            for entity in direct_entities:
                entity_id = entity.get("id")
                if entity_id:
                    consolidated[entity_id] = entity

            # Add indirect entities (will overwrite if duplicate, which is fine)
            for entity in indirect_entities:
                entity_id = entity.get("id")
                if entity_id:
                    consolidated[entity_id] = entity

            result = list(consolidated.values())
            logger.info(
                f"Consolidated {len(direct_entities)} direct + {len(indirect_entities)} indirect = {len(result)} unique entities"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to consolidate entities: {str(e)}")
            return (
                direct_entities + indirect_entities
            )  # Fallback to simple concatenation

    async def _process_products_batch(
        self,
        shop_id: str,
        products: List[Dict[str, Any]],
        batch_size: int,
        results: Dict[str, Any],
    ) -> None:
        """Process products in batches"""
        try:
            if not products:
                return

            for i in range(0, len(products), batch_size):
                batch_raw = products[i : i + batch_size]
                # Convert raw data to Pydantic models
                batch_models = [ShopifyProduct(**product) for product in batch_raw]
                batch_result = await self.compute_and_save_product_features_batch(
                    shop_id, batch_models, shop_id
                )
                results["products"]["saved_count"] += batch_result.get("saved_count", 0)
                results["products"]["total_products"] += len(batch_models)

            logger.info(f"Processed {len(products)} products in batches")
        except Exception as e:
            logger.error(f"Failed to process products batch: {str(e)}")

    async def _process_customers_batch(
        self,
        shop_id: str,
        customers: List[Dict[str, Any]],
        batch_size: int,
        results: Dict[str, Any],
    ) -> None:
        """Process customers in batches with their related orders and events"""
        try:
            if not customers:
                return

            for i in range(0, len(customers), batch_size):
                batch_raw = customers[i : i + batch_size]

                # Extract customer IDs for fetching related data
                customer_ids = [
                    customer.get("id") for customer in batch_raw if customer.get("id")
                ]

                # Fetch orders and events for this batch of customers
                orders_raw = await self.repository.get_orders_for_customer_ids(
                    shop_id, customer_ids
                )
                events_raw = await self.repository.get_events_for_customer_ids(
                    shop_id, customer_ids
                )

                # Convert raw data to Pydantic models
                batch_models = [ShopifyCustomer(**customer) for customer in batch_raw]
                orders_models = [ShopifyOrder(**order) for order in orders_raw]
                events_models = [BehavioralEvent(**event) for event in events_raw]

                batch_result = await self.compute_and_save_customer_features_batch(
                    shop_id, batch_models, orders_models, events_models
                )
                results["customers"]["saved_count"] += batch_result.get(
                    "saved_count", 0
                )
                results["customers"]["total_customers"] += len(batch_models)

            logger.info(
                f"Processed {len(customers)} customers in batches with related data"
            )
        except Exception as e:
            logger.error(f"Failed to process customers batch: {str(e)}")

    async def _process_collections_batch(
        self,
        shop_id: str,
        collections: List[Dict[str, Any]],
        batch_size: int,
        results: Dict[str, Any],
    ) -> None:
        """Process collections in batches"""
        try:
            if not collections:
                return

            for i in range(0, len(collections), batch_size):
                batch_raw = collections[i : i + batch_size]
                # Convert raw data to Pydantic models
                batch_models = [
                    ShopifyCollection(**collection) for collection in batch_raw
                ]
                batch_result = await self.compute_and_save_collection_features_batch(
                    shop_id, batch_models, shop_id
                )
                results["collections"]["saved_count"] += batch_result.get(
                    "saved_count", 0
                )
                results["collections"]["total_collections"] += len(batch_models)

            logger.info(f"Processed {len(collections)} collections in batches")
        except Exception as e:
            logger.error(f"Failed to process collections batch: {str(e)}")

    async def compute_and_save_interaction_features_batch(
        self,
        shop_id: str,
        customers: List[ShopifyCustomer],
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        events: List[BehavioralEvent],
    ) -> Dict[str, Any]:
        """Compute and save customer-product interaction features in batch"""
        try:
            logger.info(
                f"Computing interaction features for {len(customers)} customers and {len(products)} products"
            )

            # Group data by customer for efficient lookup
            orders_by_customer = {}
            events_by_customer = {}

            for order in orders:
                customer_id = order.customerId
                if customer_id:
                    if customer_id not in orders_by_customer:
                        orders_by_customer[customer_id] = []
                    orders_by_customer[customer_id].append(order)

            for event in events:
                customer_id = event.customerId
                if customer_id:
                    if customer_id not in events_by_customer:
                        events_by_customer[customer_id] = []
                    events_by_customer[customer_id].append(event)

            # Prepare batch data for interaction features
            interaction_features_batch = []
            processed_count = 0

            # For each customer-product pair, compute interaction features
            for customer in customers:
                customer_id = customer.id
                customer_orders = orders_by_customer.get(customer_id, [])
                customer_events = events_by_customer.get(customer_id, [])

                # Only process customers with some interaction history
                if not customer_orders and not customer_events:
                    continue

                context = {
                    "shop_id": shop_id,
                    "orders": customer_orders,
                    "events": customer_events,
                    "products": products,
                }

                # Compute interaction features for each product
                for product in products:
                    try:
                        interaction_features = (
                            await self.interaction_generator.generate_features(
                                customer, product, context
                            )
                        )

                        if interaction_features:
                            interaction_features_batch.append(
                                (
                                    shop_id,
                                    customer_id,
                                    product.id,
                                    interaction_features,
                                    now_utc(),
                                )
                            )
                            processed_count += 1

                    except Exception as e:
                        logger.warning(
                            f"Failed to compute interaction features for customer {customer_id}, product {product.id}: {str(e)}"
                        )
                        continue

            # Save interaction features in batch
            saved_count = 0
            if interaction_features_batch:
                saved_count = await self.repository.save_interaction_features_batch(
                    interaction_features_batch
                )
                logger.info(f"Saved {saved_count} interaction features")

            return {
                "processed_count": processed_count,
                "saved_count": saved_count,
                "total_customers": len(customers),
                "total_products": len(products),
            }

        except Exception as e:
            logger.error(f"Failed to compute interaction features batch: {str(e)}")
            return {
                "processed_count": 0,
                "saved_count": 0,
                "total_customers": len(customers),
                "total_products": len(products),
                "error": str(e),
            }
