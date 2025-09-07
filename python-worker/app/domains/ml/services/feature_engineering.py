"""
Refactored Feature engineering service implementation for BetterBundle Python Worker
This service now uses the new architecture with specialized generators and repository
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from ..interfaces.feature_engineering import IFeatureEngineeringService
from ..models import MLFeatures
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
    CollectionFeatureGenerator,
    UserFeatureGenerator,
    InteractionFeatureGenerator,
    SessionFeatureGenerator,
    CustomerBehaviorFeatureGenerator,
    SearchProductFeatureGenerator,
    ProductPairFeatureGenerator,
)

logger = get_logger(__name__)


class FeatureEngineeringService(IFeatureEngineeringService):
    """Refactored feature engineering service using new architecture"""

    def __init__(
        self,
        repository: Optional[IFeatureRepository] = None,
    ):
        # Initialize core components
        self.repository = repository or FeatureRepository()

        # Initialize feature generators for computation
        self.product_generator = ProductFeatureGenerator()
        self.user_generator = UserFeatureGenerator()
        self.interaction_generator = InteractionFeatureGenerator()
        self.collection_generator = CollectionFeatureGenerator()
        self.session_generator = SessionFeatureGenerator()
        self.customer_behavior_generator = CustomerBehaviorFeatureGenerator()
        self.search_product_generator = SearchProductFeatureGenerator()
        self.product_pair_generator = ProductPairFeatureGenerator()

    # Batch processing methods for efficiency
    async def compute_all_product_features(
        self,
        products: List[ShopifyProduct],
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute features for multiple products"""
        try:
            results = {}
            context = {
                "shop": shop,
                "orders": orders or [],
                "collections": collections or [],
                "behavioral_events": behavioral_events or [],
            }

            for product in products:
                try:
                    features = await self.product_generator.generate_features(
                        product, context
                    )
                    results[product.id] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute features for product {product.id}: {str(e)}"
                    )
                    results[product.id] = {}

            return results
        except Exception as e:
            logger.error(f"Failed to batch compute product features: {str(e)}")
            return {}

    async def compute_all_user_features(
        self,
        customers: List[ShopifyCustomer],
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute features for multiple customers/users"""
        try:
            results = {}
            context = {
                "shop": shop,
                "orders": orders or [],
                "events": events or [],
            }

            for customer in customers:
                try:
                    features = await self.user_generator.generate_features(
                        customer, context
                    )
                    results[customer.id] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute user features for {customer.id}: {str(e)}"
                    )
                    results[customer.id] = {}

            return results
        except Exception as e:
            logger.error(f"Failed to batch compute user features: {str(e)}")
            return {}

    async def compute_all_collection_features(
        self,
        collections: List[ShopifyCollection],
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
        order_data: Optional[List[ShopifyOrder]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute features for multiple collections"""
        try:
            results = {}
            context = {
                "shop": shop,
                "products": products or [],
                "behavioral_events": behavioral_events or [],
                "order_data": order_data or [],
            }

            for collection in collections:
                try:
                    features = await self.collection_generator.generate_features(
                        collection, context
                    )
                    results[collection.id] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute collection features for {collection.id}: {str(e)}"
                    )
                    results[collection.id] = {}

            return results
        except Exception as e:
            logger.error(f"Failed to batch compute collection features: {str(e)}")
            return {}

    async def compute_all_customer_behavior_features(
        self,
        customers: List[ShopifyCustomer],
        shop: ShopifyShop,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute customer behavior features"""
        try:
            results = {}

            for customer in customers:
                try:
                    # Filter events for this customer
                    customer_events = [
                        event
                        for event in (behavioral_events or [])
                        if event.customerId == customer.id
                    ]

                    context = {
                        "shop": shop,
                        "behavioral_events": customer_events,
                    }

                    features = await self.customer_behavior_generator.generate_features(
                        customer, context
                    )
                    results[customer.id] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute customer behavior features for {customer.id}: {str(e)}"
                    )
                    results[customer.id] = {}

            return results
        except Exception as e:
            logger.error(
                f"Failed to batch compute customer behavior features: {str(e)}"
            )
            return {}

    async def generate_session_features_from_events(
        self,
        behavioral_events: List[BehavioralEvent],
        shop: ShopifyShop,
        order_data: Optional[List[ShopifyOrder]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Generate session features by grouping behavioral events into sessions"""
        try:
            results = {}

            # Group events by session/customer
            sessions = self._group_events_into_sessions(behavioral_events)

            context = {
                "shop": shop,
                "order_data": order_data or [],
            }

            for session_id, session_info in sessions.items():
                try:
                    session_data = {
                        "sessionId": session_id,
                        "customerId": session_info.get("customerId"),
                        "events": session_info.get("events", []),
                    }

                    features = await self.session_generator.generate_features(
                        session_data, context
                    )
                    results[session_id] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute session features for {session_id}: {str(e)}"
                    )
                    results[session_id] = {}

            return results
        except Exception as e:
            logger.error(f"Failed to generate session features from events: {str(e)}")
            return {}

    def _group_events_into_sessions(
        self, events: List[BehavioralEvent], session_timeout_minutes: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """Group behavioral events into sessions"""
        from datetime import datetime, timedelta
        from collections import defaultdict

        sessions = defaultdict(lambda: {"events": [], "customerId": None})

        # Sort events by time
        sorted_events = sorted(
            events, key=lambda e: e.occurredAt if e.occurredAt else datetime.min
        )

        current_sessions = {}  # customer_id -> current_session_id

        for event in sorted_events:
            customer_id = event.customerId or "anonymous"
            event_time = event.occurredAt

            # Check if we need to start a new session for this customer
            should_start_new_session = True

            if customer_id in current_sessions:
                current_session_id = current_sessions[customer_id]
                last_event_time = (
                    sessions[current_session_id]["events"][-1].occurredAt
                    if sessions[current_session_id]["events"]
                    else None
                )

                if last_event_time and event_time:
                    time_diff = (event_time - last_event_time).total_seconds() / 60
                    if time_diff <= session_timeout_minutes:
                        should_start_new_session = False

            if should_start_new_session:
                # Create new session
                import uuid

                session_id = (
                    f"{customer_id}_{event_time.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
                    if event_time
                    else f"{customer_id}_{str(uuid.uuid4())[:8]}"
                )
                current_sessions[customer_id] = session_id
                sessions[session_id]["customerId"] = (
                    customer_id if customer_id != "anonymous" else None
                )

            # Add event to current session
            current_session_id = current_sessions[customer_id]
            sessions[current_session_id]["events"].append(event)

        return dict(sessions)

    async def run_comprehensive_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 500, incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Complete feature engineering pipeline with data loading, processing, and saving
        Handles all complexity internally including parallel computation and incremental logic
        """
        try:
            from ..repositories.feature_repository import FeatureRepository

            repository = FeatureRepository()

            logger.info(
                f"Starting comprehensive pipeline for shop: {shop_id} (incremental: {incremental})"
            )

            # Load shop data
            shop_data = await repository.get_shop_data(shop_id)
            if not shop_data:
                return {
                    "success": False,
                    "error": f"Shop {shop_id} not found",
                    "timestamp": now_utc().isoformat(),
                }

            # Handle incremental vs full data loading internally
            if incremental:
                last_computation_time = (
                    await repository.get_last_feature_computation_time(shop_id)
                )

                # Load recent data only
                products = await repository.get_products_batch(
                    shop_id, limit=batch_size * 2, updated_since=last_computation_time
                )
                customers = await repository.get_customers_batch(
                    shop_id, limit=batch_size, updated_since=last_computation_time
                )
                orders = await repository.get_orders_batch(
                    shop_id, limit=batch_size * 3, created_since=last_computation_time
                )
                collections = await repository.get_collections_batch(
                    shop_id, updated_since=last_computation_time
                )
                behavioral_events = await repository.get_behavioral_events_batch(
                    shop_id, limit=batch_size * 5, occurred_since=last_computation_time
                )

                # If no recent data, skip processing
                if not any(
                    [products, customers, orders, collections, behavioral_events]
                ):
                    return {
                        "success": True,
                        "shop_id": shop_id,
                        "message": "No recent data to process",
                        "incremental": True,
                        "timestamp": now_utc().isoformat(),
                    }
            else:
                # Load all data
                products = await repository.get_products_batch(
                    shop_id, limit=batch_size * 2
                )
                customers = await repository.get_customers_batch(
                    shop_id, limit=batch_size
                )
                orders = await repository.get_orders_batch(
                    shop_id, limit=batch_size * 3
                )
                collections = await repository.get_collections_batch(shop_id)
                behavioral_events = await repository.get_behavioral_events_batch(
                    shop_id, limit=batch_size * 5
                )

            logger.info(
                f"Loaded {len(products)} products, {len(customers)} customers, "
                f"{len(orders)} orders, {len(collections)} collections, {len(behavioral_events)} events"
            )

            # Compute all features using existing method
            all_features = await self.compute_all_features_for_shop(
                shop=shop_data,
                products=products,
                customers=customers,
                orders=orders,
                collections=collections,
                behavioral_events=behavioral_events,
            )

            # Save all features to database with parallel processing
            save_results = await self._save_all_features_with_parallel_processing(
                shop_id, all_features
            )

            # Update timestamp for incremental processing
            if incremental:
                await repository.update_last_feature_computation_time(
                    shop_id, now_utc()
                )

            return {
                "success": True,
                "shop_id": shop_id,
                "results": save_results,
                "incremental": incremental,
                "data_loaded": {
                    "products": len(products),
                    "customers": len(customers),
                    "orders": len(orders),
                    "collections": len(collections),
                    "behavioral_events": len(behavioral_events),
                },
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Comprehensive pipeline failed for shop {shop_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "shop_id": shop_id,
                "timestamp": now_utc().isoformat(),
            }

    async def compute_all_features_for_shop(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Comprehensive feature computation for all entities in a shop"""
        try:
            all_features = {}

            # Prepare data
            products = products or []
            orders = orders or []
            customers = customers or []
            collections = collections or []
            behavioral_events = behavioral_events or []

            logger.info(f"Computing comprehensive features for shop {shop.id}")

            # 1. Product Features
            logger.info("Computing product features...")
            product_features = await self.compute_all_product_features(
                products, shop, orders, collections, behavioral_events
            )
            all_features["products"] = product_features

            # 2. User/Customer Features
            logger.info("Computing user features...")
            user_features = await self.compute_all_user_features(
                customers, shop, orders, behavioral_events
            )
            all_features["users"] = user_features

            # 3. Collection Features
            logger.info("Computing collection features...")
            collection_features = await self.compute_all_collection_features(
                collections, shop, products, behavioral_events, orders
            )
            all_features["collections"] = collection_features

            # 4. Customer Behavior Features
            logger.info("Computing customer behavior features...")
            behavior_features = await self.compute_all_customer_behavior_features(
                customers, shop, behavioral_events
            )
            all_features["customer_behaviors"] = behavior_features

            # 5. Session Features
            logger.info("Computing session features...")
            session_features = await self.generate_session_features_from_events(
                behavioral_events, shop, orders
            )
            all_features["sessions"] = session_features

            # 6. Interaction Features (sample of customer-product pairs)
            logger.info("Computing interaction features...")
            interaction_features = await self._compute_sample_interaction_features(
                customers, products, shop, orders, behavioral_events
            )
            all_features["interactions"] = interaction_features

            # 7. Product Pair Features (top product pairs)
            logger.info("Computing product pair features...")
            product_pair_features = await self._compute_top_product_pair_features(
                products, shop, orders, behavioral_events
            )
            all_features["product_pairs"] = product_pair_features

            # 8. Search Product Features (from search events)
            logger.info("Computing search product features...")
            search_product_features = (
                await self._compute_search_product_features_from_events(
                    behavioral_events, shop
                )
            )
            all_features["search_products"] = search_product_features

            logger.info(
                f"Completed comprehensive feature computation for shop {shop.id}"
            )
            return all_features

        except Exception as e:
            logger.error(f"Failed to compute comprehensive shop features: {str(e)}")
            return {}

    async def _save_all_features_with_parallel_processing(
        self, shop_id: str, all_features: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Save all features to database with optimized parallel processing using repository bulk operations"""
        import asyncio

        save_results = {}
        save_tasks = []

        # Feature type configuration for DRY approach
        feature_configs = [
            ("products", "product", all_features.get("products", {})),
            ("users", "user", all_features.get("users", {})),
            ("collections", "collection", all_features.get("collections", {})),
            (
                "customer_behaviors",
                "customer_behavior",
                all_features.get("customer_behaviors", {}),
            ),
            ("sessions", "session", all_features.get("sessions", {})),
            ("interactions", "interaction", all_features.get("interactions", {})),
            ("product_pairs", "product_pair", all_features.get("product_pairs", {})),
            (
                "search_products",
                "search_product",
                all_features.get("search_products", {}),
            ),
        ]

        # Create parallel save tasks using generic method
        for feature_key, feature_type, features in feature_configs:
            if features:
                save_tasks.append(
                    self._save_features_generic(
                        shop_id, feature_key, feature_type, features
                    )
                )

        # Execute all save operations in parallel
        if save_tasks:
            results = await asyncio.gather(*save_tasks, return_exceptions=True)

            # Combine results from parallel tasks
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Parallel save task failed: {str(result)}")
                elif isinstance(result, dict):
                    save_results.update(result)

        return save_results

    async def _save_features_generic(
        self,
        shop_id: str,
        feature_key: str,
        feature_type: str,
        features: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Generic method to save any feature type - eliminates duplicate methods"""
        try:
            saved_count = 0

            # Prepare batch data for bulk operation
            batch_data = []

            for entity_id, feature_data in features.items():
                if feature_data:
                    # Handle different feature types that may need key splitting
                    if feature_type in [
                        "interaction",
                        "product_pair",
                        "search_product",
                    ]:
                        if "-" in entity_id:
                            if feature_type == "interaction":
                                customer_id, product_id = entity_id.split("-", 1)
                                batch_data.append(
                                    (shop_id, customer_id, product_id, feature_data)
                                )
                            elif feature_type == "product_pair":
                                product_id1, product_id2 = entity_id.split("-", 1)
                                batch_data.append(
                                    (shop_id, product_id1, product_id2, feature_data)
                                )
                            elif feature_type == "search_product":
                                search_query, product_id = entity_id.split("-", 1)
                                batch_data.append(
                                    (shop_id, search_query, product_id, feature_data)
                                )
                    else:
                        # Simple entity types (product, user, collection, etc.)
                        batch_data.append((shop_id, entity_id, feature_data))

            # Use repository bulk operations for efficiency
            if batch_data:
                bulk_method_name = f"bulk_upsert_{feature_type}_features"
                if hasattr(self.repository, bulk_method_name):
                    bulk_method = getattr(self.repository, bulk_method_name)
                    saved_count = await bulk_method(batch_data)
                else:
                    # Fallback to individual saves if bulk method doesn't exist
                    for data in batch_data:
                        save_method_name = f"save_{feature_type}_features"
                        if hasattr(self.repository, save_method_name):
                            save_method = getattr(self.repository, save_method_name)
                            await save_method(*data)
                            saved_count += 1

            logger.info(
                f"Saved {saved_count} {feature_type} feature records using bulk operations"
            )
            return {
                feature_key: {
                    "saved_count": saved_count,
                    "total_processed": len(features),
                }
            }

        except Exception as e:
            logger.error(f"Failed to save {feature_type} features: {str(e)}")
            return {
                feature_key: {
                    "saved_count": 0,
                    "total_processed": len(features),
                    "error": str(e),
                }
            }

    async def _compute_sample_interaction_features(
        self,
        customers: List[ShopifyCustomer],
        products: List[ShopifyProduct],
        shop: ShopifyShop,
        orders: List[ShopifyOrder],
        behavioral_events: List[BehavioralEvent],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute interaction features for customer-product pairs that have actual interactions"""
        try:
            results = {}

            # Find customer-product pairs that have interactions
            interaction_pairs = set()

            # From orders
            for order in orders:
                if order.customer_id:
                    for line_item in order.line_items:
                        if hasattr(line_item, "product_id"):
                            interaction_pairs.add(
                                (order.customer_id, line_item.product_id)
                            )

            # From behavioral events
            for event in behavioral_events:
                if event.customerId and hasattr(event, "eventData"):
                    product_id = self._extract_product_id_from_event(event)
                    if product_id:
                        interaction_pairs.add((event.customerId, product_id))

            # Compute features for these pairs (limit to prevent excessive computation)
            limited_pairs = list(interaction_pairs)[:1000]  # Limit to 1000 pairs

            for customer_id, product_id in limited_pairs:
                try:
                    # Find customer and product objects
                    customer = next((c for c in customers if c.id == customer_id), None)
                    product = next((p for p in products if p.id == product_id), None)

                    if customer and product:
                        features = await self.compute_interaction_features(
                            customer, product, shop, orders, behavioral_events
                        )
                        results[f"{customer_id}-{product_id}"] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute interaction features for {customer_id}-{product_id}: {str(e)}"
                    )

            return results
        except Exception as e:
            logger.error(f"Failed to compute sample interaction features: {str(e)}")
            return {}

    async def _compute_top_product_pair_features(
        self,
        products: List[ShopifyProduct],
        shop: ShopifyShop,
        orders: List[ShopifyOrder],
        behavioral_events: List[BehavioralEvent],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute product pair features for frequently co-occurring products"""
        try:
            results = {}

            # Find frequently co-occurring product pairs from orders
            co_occurrence_counts = {}

            for order in orders:
                product_ids = [
                    item.product_id
                    for item in order.line_items
                    if hasattr(item, "product_id")
                ]

                # Create pairs
                for i in range(len(product_ids)):
                    for j in range(i + 1, len(product_ids)):
                        pair = tuple(sorted([product_ids[i], product_ids[j]]))
                        co_occurrence_counts[pair] = (
                            co_occurrence_counts.get(pair, 0) + 1
                        )

            # Get top pairs (limit to prevent excessive computation)
            top_pairs = sorted(
                co_occurrence_counts.items(), key=lambda x: x[1], reverse=True
            )[:100]

            for (product_id1, product_id2), count in top_pairs:
                try:
                    features = await self.compute_product_pair_features(
                        product_id1, product_id2, shop, orders, behavioral_events
                    )
                    results[f"{product_id1}-{product_id2}"] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute product pair features for {product_id1}-{product_id2}: {str(e)}"
                    )

            return results
        except Exception as e:
            logger.error(f"Failed to compute top product pair features: {str(e)}")
            return {}

    async def _compute_search_product_features_from_events(
        self,
        behavioral_events: List[BehavioralEvent],
        shop: ShopifyShop,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute search-product features from search events"""
        try:
            results = {}

            # Find search query - product combinations
            search_product_combinations = set()

            for event in behavioral_events:
                if event.eventType == "search_submitted" and hasattr(
                    event, "eventData"
                ):
                    # Extract search query
                    query = self._extract_search_query_from_event(event)
                    if query:
                        # Look for product interactions after this search
                        # For now, we'll use a simple approach
                        search_product_combinations.add((query, "sample_product"))

            # Limit combinations
            limited_combinations = list(search_product_combinations)[:100]

            for search_query, product_id in limited_combinations:
                try:
                    features = await self.compute_search_product_features(
                        search_query, product_id, shop, behavioral_events
                    )
                    results[f"{search_query}-{product_id}"] = features
                except Exception as e:
                    logger.error(
                        f"Failed to compute search-product features for {search_query}-{product_id}: {str(e)}"
                    )

            return results
        except Exception as e:
            logger.error(
                f"Failed to compute search-product features from events: {str(e)}"
            )
            return {}

    def _extract_product_id_from_event(self, event: BehavioralEvent) -> Optional[str]:
        """Extract product ID from behavioral event"""
        try:
            if hasattr(event, "eventData") and event.eventData:
                if isinstance(event.eventData, dict):
                    return event.eventData.get("productId") or event.eventData.get(
                        "product_id"
                    )
            return None
        except Exception:
            return None

    def _extract_search_query_from_event(self, event: BehavioralEvent) -> Optional[str]:
        """Extract search query from search event"""
        try:
            if hasattr(event, "eventData") and event.eventData:
                if isinstance(event.eventData, dict):
                    return (
                        event.eventData.get("query")
                        or event.eventData.get("searchQuery")
                        or event.eventData.get("q")
                    )
            return None
        except Exception:
            return None

    async def compute_cross_entity_features(
        self,
        shop: ShopifyShop,
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        customers: List[ShopifyCustomer],
        collections: List[ShopifyCollection],
        events: List[BehavioralEvent],
    ) -> Dict[str, Any]:
        """Compute cross-entity ML features (legacy method - use compute_all_features_for_shop instead)"""
        try:
            features = {}

            # Product-customer interactions
            features.update(
                self._compute_product_customer_interactions(products, customers, orders)
            )

            # Collection performance features
            features.update(
                self._compute_collection_performance_features_batch(
                    collections, products, orders
                )
            )

            # Customer segment features
            features.update(
                self._compute_customer_segment_features(customers, orders, events)
            )

            # Product category features
            features.update(
                self._compute_product_category_features(products, collections)
            )

            # Time series features
            features.update(self._compute_time_series_features(orders, events))

            return features

        except Exception as e:
            logger.error(f"Failed to compute cross-entity features: {str(e)}")
            return {}

    async def create_ml_features(
        self,
        shop_id: str,
        feature_type: str,
        entity_id: str,
        features: Dict[str, Any],
        data_sources: List[str],
    ) -> MLFeatures:
        """Create MLFeatures model instance"""
        try:
            return MLFeatures(
                shop_id=shop_id,
                feature_type=feature_type,
                entity_id=entity_id,
                features=features,
                data_sources=data_sources,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
        except Exception as e:
            logger.error(f"Failed to create MLFeatures: {str(e)}")
            raise
