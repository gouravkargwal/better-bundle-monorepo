"""
Refactored Feature engineering service implementation for BetterBundle Python Worker
This service now uses the new architecture with specialized generators and repository
"""

from typing import Dict, Any, List, Optional
import asyncio

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from ..interfaces.feature_engineering import IFeatureEngineeringService

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

    def _build_base_context(self, shop: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Build base context dictionary with common fields"""
        return {"shop": shop, "timestamp": now_utc(), **kwargs}

    async def _compute_feature_safely(
        self,
        generator,
        *args,
        entity_id: str = "unknown",
        feature_type: str = "unknown",
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Safely compute features with standardized error handling

        Args:
            generator: Feature generator instance
            *args: Arguments to pass to generate_features
            entity_id: ID of entity being processed (for logging)
            feature_type: Type of feature being computed (for logging)
            **kwargs: Additional keyword arguments

        Returns:
            Computed features or None if failed
        """
        try:
            if not hasattr(generator, "generate_features"):
                logger.error(
                    f"Generator {generator.__class__.__name__} has no generate_features method"
                )
                return None

            return await generator.generate_features(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Failed to compute {feature_type} features for {entity_id}: {str(e)}"
            )
            return None

    async def _process_entities_batch(
        self,
        entities: List[Dict[str, Any]],
        generator,
        context: Dict[str, Any],
        entity_key: str,
        feature_type: str,
        max_concurrent: int = 10,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process a batch of entities with standardized patterns

        Args:
            entities: List of entities to process
            generator: Feature generator instance
            context: Context data for feature computation
            entity_key: Key to extract entity ID from entity dict
            feature_type: Type of feature being computed
            max_concurrent: Maximum concurrent operations

        Returns:
            Dictionary mapping entity IDs to computed features
        """
        if not entities:
            return {}

        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_entity(entity):
            async with semaphore:
                entity_id = entity.get(entity_key, "unknown")

                # Handle different generator signatures
                if generator.__class__.__name__ == "ProductFeatureGenerator":
                    features = await self._compute_feature_safely(
                        generator,
                        context.get("shop", {}).get("id", ""),
                        entity.get("productId", ""),
                        context,
                        entity_id=entity_id,
                        feature_type=feature_type,
                    )
                elif generator.__class__.__name__ == "UserFeatureGenerator":
                    features = await self._compute_feature_safely(
                        generator,
                        context.get("shop", {}).get("id", ""),
                        entity.get("customerId", ""),
                        context,
                        entity_id=entity_id,
                        feature_type=feature_type,
                    )
                else:
                    features = await self._compute_feature_safely(
                        generator,
                        entity,
                        context,
                        entity_id=entity_id,
                        feature_type=feature_type,
                    )

                if features:
                    results[entity_id] = features

        # Execute all computations in parallel
        tasks = [process_single_entity(entity) for entity in entities]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def process_entities_in_chunks(
        self,
        shop_id: str,
        entity_type: str,
        batch_size: int,
        chunk_size: int = 100,
        incremental: bool = False,
        since_timestamp: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Process entities in chunks to avoid loading large datasets in memory

        Args:
            shop_id: Shop ID to process
            entity_type: Type of entity ('products', 'customers', 'orders', 'collections', 'behavioral_events')
            batch_size: Total batch size to process
            chunk_size: Size of each chunk to process in memory
            incremental: Whether to use incremental loading
            since_timestamp: Timestamp for incremental loading

        Returns:
            List of all processed entities
        """
        all_entities = []
        offset = 0

        while True:
            current_chunk_size = min(chunk_size, batch_size)

            try:
                if incremental and since_timestamp:
                    # Use incremental loading methods
                    if entity_type == "products":
                        chunk = await self.repository.get_products_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "customers":
                        chunk = await self.repository.get_customers_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "orders":
                        chunk = await self.repository.get_orders_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "collections":
                        chunk = await self.repository.get_collections_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "behavioral_events":
                        chunk = await self.repository.get_behavioral_events_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    else:
                        logger.error(
                            f"Unknown entity type for incremental loading: {entity_type}"
                        )
                        break
                else:
                    # Use regular batch loading methods
                    if entity_type == "products":
                        chunk = await self.repository.get_products_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "customers":
                        chunk = await self.repository.get_customers_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "orders":
                        chunk = await self.repository.get_orders_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "collections":
                        chunk = await self.repository.get_collections_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "behavioral_events":
                        chunk = await self.repository.get_behavioral_events_batch(
                            shop_id, current_chunk_size, offset
                        )
                    else:
                        logger.error(f"Unknown entity type: {entity_type}")
                        break

                if not chunk:
                    # No more data available
                    break

                all_entities.extend(chunk)
                offset += len(chunk)

                logger.debug(
                    f"Loaded chunk of {len(chunk)} {entity_type} (total: {len(all_entities)})"
                )

                # If we got fewer entities than requested, we've reached the end
                if len(chunk) < current_chunk_size:
                    break

            except Exception as e:
                logger.error(
                    f"Failed to load chunk of {entity_type} at offset {offset}: {str(e)}"
                )
                break

        logger.info(f"Loaded {len(all_entities)} {entity_type} in chunks")
        return all_entities

    async def compute_all_collection_features(
        self,
        collections: List[Dict[str, Any]],
        shop: Dict[str, Any],
        products: Optional[List[Dict[str, Any]]] = None,
        behavioral_events: Optional[List[Dict[str, Any]]] = None,
        order_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute features for multiple collections"""
        try:
            context = self._build_base_context(
                shop,
                products=products or [],
                behavioral_events=behavioral_events or [],
                order_data=order_data or [],
            )

            return await self._process_entities_batch(
                collections, self.collection_generator, context, "id", "collection"
            )
        except Exception as e:
            logger.error(f"Failed to batch compute collection features: {str(e)}")
            return {}

    async def compute_all_customer_behavior_features(
        self,
        customers: List[Dict[str, Any]],
        shop: Dict[str, Any],
        behavioral_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute customer behavior features"""
        try:
            results = {}

            for customer in customers:
                # Filter events for this customer
                customer_events = [
                    event
                    for event in (behavioral_events or [])
                    if event.get("customerId") == customer["id"]
                ]

                context = self._build_base_context(
                    shop, behavioral_events=customer_events
                )

                features = await self._compute_feature_safely(
                    self.customer_behavior_generator,
                    customer,
                    context,
                    entity_id=customer["id"],
                    feature_type="customer_behavior",
                )

                if features:
                    results[customer["id"]] = features

            return results
        except Exception as e:
            logger.error(
                f"Failed to batch compute customer behavior features: {str(e)}"
            )
            return {}

    async def generate_session_features_from_events(
        self,
        behavioral_events: List[Dict[str, Any]],
        shop: Dict[str, Any],
        order_data: Optional[List[Dict[str, Any]]] = None,
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
                session_data = {
                    "sessionId": session_id,
                    "customerId": session_info.get("customerId"),
                    "events": session_info.get("events", []),
                }

                features = await self._compute_feature_safely(
                    self.session_generator,
                    session_data,
                    context,
                    entity_id=session_id,
                    feature_type="session",
                )

                if features:
                    results[session_id] = features

            return results
        except Exception as e:
            logger.error(f"Failed to generate session features from events: {str(e)}")
            return {}

    def _group_events_into_sessions(
        self, events: List[Dict[str, Any]], session_timeout_minutes: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """Group behavioral events into sessions"""
        from datetime import datetime, timedelta
        from collections import defaultdict

        sessions = defaultdict(lambda: {"events": [], "customerId": None})

        # Sort events by time
        sorted_events = sorted(
            events,
            key=lambda e: e.get("timestamp") if e.get("timestamp") else datetime.min,
        )

        current_sessions = {}  # customer_id -> current_session_id

        for event in sorted_events:
            customer_id = event.get("customerId") or "anonymous"
            event_time = event.get("timestamp")

            # Check if we need to start a new session for this customer
            should_start_new_session = True

            if customer_id in current_sessions:
                current_session_id = current_sessions[customer_id]
                last_event_time = (
                    sessions[current_session_id]["events"][-1].get("timestamp")
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

            # Handle incremental vs full data loading with chunked processing
            if incremental:
                last_computation_time = (
                    await repository.get_last_feature_computation_time(shop_id)
                )
                logger.info(
                    f"Using incremental processing since: {last_computation_time}"
                )

                # Load only data modified since last computation using chunked processing
                products = await self.process_entities_in_chunks(
                    shop_id,
                    "products",
                    batch_size * 2,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                customers = await self.process_entities_in_chunks(
                    shop_id,
                    "customers",
                    batch_size,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                orders = await self.process_entities_in_chunks(
                    shop_id,
                    "orders",
                    batch_size * 3,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                collections = await self.process_entities_in_chunks(
                    shop_id,
                    "collections",
                    batch_size,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                behavioral_events = await self.process_entities_in_chunks(
                    shop_id,
                    "behavioral_events",
                    batch_size * 5,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )

                # If no recent data, skip processing
                if not any(
                    [products, customers, orders, collections, behavioral_events]
                ):
                    logger.info(
                        f"No data changes detected since {last_computation_time}. Skipping feature computation."
                    )
                    return {
                        "success": True,
                        "shop_id": shop_id,
                        "message": "No recent data to process - incremental processing skipped",
                        "incremental": True,
                        "timestamp": now_utc().isoformat(),
                        "results": {
                            "products": {"saved_count": 0, "total_processed": 0},
                            "users": {"saved_count": 0, "total_processed": 0},
                            "collections": {"saved_count": 0, "total_processed": 0},
                            "customer_behaviors": {
                                "saved_count": 0,
                                "total_processed": 0,
                            },
                        },
                    }
            else:
                # Load all data using chunked processing
                products = await self.process_entities_in_chunks(
                    shop_id, "products", batch_size * 2, chunk_size=100
                )
                customers = await self.process_entities_in_chunks(
                    shop_id, "customers", batch_size, chunk_size=100
                )
                orders = await self.process_entities_in_chunks(
                    shop_id, "orders", batch_size * 3, chunk_size=100
                )
                collections = await self.process_entities_in_chunks(
                    shop_id, "collections", batch_size, chunk_size=100
                )
                behavioral_events = await self.process_entities_in_chunks(
                    shop_id, "behavioral_events", batch_size * 5, chunk_size=100
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

            # Check if all feature types succeeded for logging purposes
            all_features_succeeded = True
            expected_feature_types = [
                "products",
                "users",
                "collections",
                "customer_behaviors",
                "interactions",
                "sessions",
                "product_pairs",
                "search_products",
            ]

            for feature_type in expected_feature_types:
                if feature_type in save_results:
                    result = save_results[feature_type]
                    if isinstance(result, dict) and result.get("saved_count", 0) == 0:
                        logger.warning(
                            f"Feature type {feature_type} had no successful saves"
                        )
                        # Don't mark as failed if there was no data to process
                        if result.get("total_processed", 0) > 0:
                            all_features_succeeded = False
                else:
                    logger.warning(
                        f"Feature type {feature_type} missing from save results"
                    )
                    all_features_succeeded = False

            # Log the overall success status (no timestamp update needed - features are self-tracking)
            if all_features_succeeded:
                logger.info(
                    f"All feature types processed successfully for shop {shop_id}"
                )
            else:
                logger.warning(
                    f"Some feature types failed for shop {shop_id} - will retry on next run"
                )

            return {
                "success": True,
                "shop_id": shop_id,
                "results": save_results,
                "incremental": incremental,
                "all_features_succeeded": all_features_succeeded,
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
        shop: Dict[str, Any],
        products: Optional[List[Dict[str, Any]]] = None,
        orders: Optional[List[Dict[str, Any]]] = None,
        customers: Optional[List[Dict[str, Any]]] = None,
        collections: Optional[List[Dict[str, Any]]] = None,
        behavioral_events: Optional[List[Dict[str, Any]]] = None,
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

            logger.info(f"Computing comprehensive features for shop {shop['id']}")

            # 1. Product Features
            logger.info("Computing product features...")
            product_context = self._build_base_context(
                shop,
                orders=orders or [],
                collections=collections or [],
                behavioral_events=behavioral_events or [],
            )
            product_features = await self._process_entities_batch(
                products,
                self.product_generator,
                product_context,
                "productId",
                "product",
            )
            all_features["products"] = product_features

            # 2. User/Customer Features
            logger.info("Computing user features...")
            user_context = self._build_base_context(
                shop, orders=orders or [], events=behavioral_events or []
            )
            user_features = await self._process_entities_batch(
                customers, self.user_generator, user_context, "customerId", "user"
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
                f"Completed comprehensive feature computation for shop {shop['id']}"
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
            # Always create save tasks, even for empty feature dictionaries
            # This ensures all expected feature types are included in save_results
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

            # Handle empty feature dictionaries
            if not features:
                logger.info(f"No {feature_type} features to save for shop {shop_id}")
                return {
                    feature_key: {
                        "saved_count": 0,
                        "total_processed": 0,
                    }
                }

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
                                # For interaction, we need to pass the feature_data directly
                                # The shop_id, customer_id, product_id are already in feature_data
                                batch_data.append(feature_data)
                            elif feature_type == "product_pair":
                                product_id1, product_id2 = entity_id.split("-", 1)
                                # For product_pair, we need to pass the feature_data directly
                                # The shop_id, product_id1, product_id2 are already in feature_data
                                batch_data.append(feature_data)
                            elif feature_type == "search_product":
                                search_query, product_id = entity_id.split("-", 1)
                                # For search_product, we need to pass the feature_data directly
                                # The shop_id, search_query, product_id are already in feature_data
                                batch_data.append(feature_data)
                    else:
                        # Simple entity types - use consistent dictionary-based approach
                        prepared_data = feature_data.copy()
                        prepared_data["shopId"] = shop_id

                        # Add entity ID based on feature type
                        if feature_type == "collection":
                            prepared_data["collectionId"] = entity_id
                        elif feature_type == "customer_behavior":
                            prepared_data["customerId"] = entity_id
                        elif feature_type == "product":
                            prepared_data["productId"] = entity_id
                        elif feature_type == "user":
                            prepared_data["customerId"] = entity_id
                        elif feature_type == "session":
                            prepared_data["sessionId"] = entity_id
                        else:
                            # Generic fallback
                            prepared_data["entityId"] = entity_id

                        batch_data.append(prepared_data)

            # Use repository bulk operations for efficiency - all methods now use dictionaries
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
                            await save_method(data)
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
        customers: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
        shop: Dict[str, Any],
        orders: List[Dict[str, Any]],
        behavioral_events: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute interaction features for customer-product pairs that have actual interactions"""
        try:
            results = {}
            logger.info(
                f"🔍 Computing interaction features: {len(customers)} customers, {len(products)} products, {len(orders)} orders, {len(behavioral_events)} events"
            )

            # Find customer-product pairs that have interactions
            interaction_pairs = set()

            # From orders
            logger.info(f"🔍 Checking orders for interaction pairs...")
            for order in orders:
                if order.get("customerId"):
                    logger.info(
                        f"🔍 Order {order.get('id', 'unknown')} has customerId: {order.get('customerId')}"
                    )
                    for line_item in order.get("lineItems", []):
                        # Extract product_id from variant.id if available
                        product_id = None
                        if "product_id" in line_item:
                            product_id = line_item.get("product_id")
                        elif "variant" in line_item and "id" in line_item["variant"]:
                            # Convert ProductVariant ID to Product ID
                            variant_id = line_item["variant"]["id"]
                            if variant_id.startswith("gid://shopify/ProductVariant/"):
                                # Extract variant number and convert to product number
                                variant_num = variant_id.split("/")[-1]
                                product_num = str(
                                    int(variant_num) - 1000
                                )  # Convert 2001 -> 1001
                                product_id = f"gid://shopify/Product/{product_num}"
                                logger.info(
                                    f"🔍 Converted variant {variant_id} to product {product_id}"
                                )

                        if product_id:
                            pair = (order.get("customerId"), product_id)
                            interaction_pairs.add(pair)
                            logger.info(f"🔍 Added order interaction pair: {pair}")
                        else:
                            logger.info(f"🔍 Line item missing product_id: {line_item}")

            # From behavioral events
            logger.info(f"🔍 Checking behavioral events for interaction pairs...")
            for event in behavioral_events:
                if event.get("customerId") and "eventData" in event:
                    product_id = self._extract_product_id_from_event(
                        event.get("eventData")
                    )
                    if product_id:
                        pair = (event.get("customerId"), product_id)
                        interaction_pairs.add(pair)
                        logger.info(f"🔍 Added event interaction pair: {pair}")
                    else:
                        event_id = event.get('id', 'unknown')
                        event_data = event.get('eventData')
                        logger.info(
                            f"🔍 Event {event_id} - no product_id extracted from eventData: {event_data}"
                        )
                else:
                    event_id = event.get('id', 'unknown')
                    customer_id = event.get('customerId')
                    has_event_data = 'eventData' in event
                    logger.info(
                        f"🔍 Event {event_id} - customerId: {customer_id}, has eventData: {has_event_data}, "
                        f"eventType: {event.get('eventType', 'unknown')}, clientId: {event.get('clientId', 'none')}"
                    )

            # Compute features for these pairs (limit to prevent excessive computation)
            limited_pairs = list(interaction_pairs)[:1000]  # Limit to 1000 pairs
            logger.info(
                f"🔍 Found {len(interaction_pairs)} total interaction pairs, processing {len(limited_pairs)}"
            )

            for customer_id, product_id in limited_pairs:
                # Find customer and product objects
                customer = next(
                    (c for c in customers if c.get("customerId") == customer_id), None
                )
                # Handle both GID format and plain product ID format
                product = None
                if product_id.startswith("gid://shopify/Product/"):
                    # Extract numeric product ID from GID
                    numeric_product_id = product_id.split("/")[-1]
                    product = next(
                        (
                            p
                            for p in products
                            if p.get("productId") == numeric_product_id
                        ),
                        None,
                    )
                else:
                    product = next(
                        (p for p in products if p.get("productId") == product_id), None
                    )

                if customer and product:
                    context = {
                        "customer": customer,
                        "product": product,
                        "shop": shop,
                        "orders": orders,
                        "behavioral_events": behavioral_events,
                    }

                    features = await self._compute_feature_safely(
                        self.interaction_generator,
                        shop["id"],
                        customer_id,
                        product_id,
                        context,
                        entity_id=f"{customer_id}-{product_id}",
                        feature_type="interaction",
                    )

                    if features:
                        results[f"{customer_id}-{product_id}"] = features

            return results
        except Exception as e:
            logger.error(f"Failed to compute sample interaction features: {str(e)}")
            return {}

    async def _compute_top_product_pair_features(
        self,
        products: List[Dict[str, Any]],
        shop: Dict[str, Any],
        orders: List[Dict[str, Any]],
        behavioral_events: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute product pair features for frequently co-occurring products"""
        try:
            results = {}
            logger.info(
                f"🔍 Computing product pair features: {len(products)} products, {len(orders)} orders"
            )

            # Find frequently co-occurring product pairs from orders
            co_occurrence_counts = {}

            for order in orders:
                line_items = order.get("lineItems", [])
                logger.info(
                    f"🔍 Order {order.get('id', 'unknown')} has {len(line_items)} line items"
                )

                product_ids = []
                for item in line_items:
                    # Extract product_id from variant.id if available
                    product_id = None
                    if "product_id" in item:
                        product_id = item.get("product_id")
                    elif "variant" in item and "id" in item["variant"]:
                        # Convert ProductVariant ID to Product ID
                        variant_id = item["variant"]["id"]
                        if variant_id.startswith("gid://shopify/ProductVariant/"):
                            # Extract variant number and convert to product number
                            variant_num = variant_id.split("/")[-1]
                            product_num = str(
                                int(variant_num) - 1000
                            )  # Convert 2001 -> 1001
                            product_id = f"gid://shopify/Product/{product_num}"
                            logger.info(
                                f"🔍 Converted variant {variant_id} to product {product_id}"
                            )

                    if product_id:
                        product_ids.append(product_id)
                logger.info(
                    f"🔍 Order {order.get('id', 'unknown')} product_ids: {product_ids}"
                )

                # Create pairs
                for i in range(len(product_ids)):
                    for j in range(i + 1, len(product_ids)):
                        pair = tuple(sorted([product_ids[i], product_ids[j]]))
                        co_occurrence_counts[pair] = (
                            co_occurrence_counts.get(pair, 0) + 1
                        )
                        logger.info(
                            f"🔍 Added product pair: {pair} (count: {co_occurrence_counts[pair]})"
                        )

            # Get top pairs (limit to prevent excessive computation)
            top_pairs = sorted(
                co_occurrence_counts.items(), key=lambda x: x[1], reverse=True
            )[:100]
            logger.info(
                f"🔍 Found {len(co_occurrence_counts)} product pairs, processing top {len(top_pairs)}"
            )

            for (product_id1, product_id2), count in top_pairs:
                context = {
                    "orders": orders,
                    "behavioral_events": behavioral_events,
                    "shop": shop,
                }

                features = await self._compute_feature_safely(
                    self.product_pair_generator,
                    shop["id"],
                    product_id1,
                    product_id2,
                    context,
                    entity_id=f"{product_id1}-{product_id2}",
                    feature_type="product_pair",
                )

                if features:
                    logger.info(f"🔍 Generated product pair features: {features}")
                    results[f"{product_id1}-{product_id2}"] = features

            return results
        except Exception as e:
            logger.error(f"Failed to compute top product pair features: {str(e)}")
            return {}

    async def _compute_search_product_features_from_events(
        self,
        behavioral_events: List[Dict[str, Any]],
        shop: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute search-product features from search events"""
        try:
            results = {}
            logger.info(
                f"🔍 Computing search product features: {len(behavioral_events)} events"
            )

            # Find search query - product combinations
            search_product_combinations = set()

            # Sort events by timestamp to find products viewed after searches
            sorted_events = sorted(
                behavioral_events, key=lambda e: e.get("timestamp", "")
            )
            logger.info(f"🔍 Sorted {len(sorted_events)} events by timestamp")

            for i, event in enumerate(sorted_events):
                logger.info(
                    f"🔍 Processing event {i}: {event.get('eventType', 'unknown')} - {event.get('id', 'unknown')}"
                )

                if (
                    event.get("eventType") == "search_submitted"
                    and "eventData" in event
                ):
                    logger.info(
                        f"🔍 Found search_submitted event: {event.get('id', 'unknown')}"
                    )

                    # Extract search query
                    query = self._extract_search_query_from_event(event)
                    logger.info(f"🔍 Extracted search query: '{query}'")

                    if query:
                        # Look for product interactions after this search
                        search_timestamp = event.get("timestamp")
                        client_id = event.get("clientId")
                        logger.info(
                            f"🔍 Search timestamp: {search_timestamp}, client_id: {client_id}"
                        )

                        # Find products viewed by the same client after this search
                        for j in range(i + 1, len(sorted_events)):
                            later_event = sorted_events[j]
                            logger.info(
                                f"🔍 Checking later event {j}: {later_event.get('eventType', 'unknown')} - client: {later_event.get('clientId', 'unknown')}"
                            )

                            logger.info(
                                f"🔍 Event {j} conditions: clientId={later_event.get('clientId')} == {client_id}? {later_event.get('clientId') == client_id}, eventType={later_event.get('eventType')} == 'product_viewed'? {later_event.get('eventType') == 'product_viewed'}, timestamp={later_event.get('timestamp')} >= {search_timestamp}? {later_event.get('timestamp') >= search_timestamp if later_event.get('timestamp') and search_timestamp else 'N/A'}"
                            )

                            if (
                                later_event.get("clientId") == client_id
                                and later_event.get("eventType") == "product_viewed"
                                and later_event.get("timestamp") >= search_timestamp
                                and "eventData" in later_event
                            ):
                                logger.info(
                                    f"🔍 Found matching product_viewed event after search!"
                                )

                                # Extract product ID from the product_viewed event
                                product_id = self._extract_product_id_from_event(
                                    later_event.get("eventData")
                                )
                                logger.info(f"🔍 Extracted product_id: {product_id}")

                                if product_id:
                                    combination = (query, product_id)
                                    search_product_combinations.add(combination)
                                    logger.info(
                                        f"🔍 Added search-product combination: {combination}"
                                    )
                                    break  # Only take the first product viewed after search
                                else:
                                    logger.info(
                                        f"🔍 No product_id extracted from eventData: {later_event.get('eventData')}"
                                    )
                    else:
                        logger.info(
                            f"🔍 No query extracted from eventData: {event.get('eventData')}"
                        )
                else:
                    logger.info(
                        f"🔍 Event {i} is not search_submitted or missing eventData"
                    )

            # Limit combinations
            limited_combinations = list(search_product_combinations)[:100]
            logger.info(
                f"🔍 Found {len(search_product_combinations)} search-product combinations, processing {len(limited_combinations)}"
            )

            for search_query, product_id in limited_combinations:
                search_product_data = {
                    "searchQuery": search_query,
                    "productId": product_id,
                }
                context = {"behavioral_events": behavioral_events, "shop": shop}

                features = await self._compute_feature_safely(
                    self.search_product_generator,
                    search_product_data,
                    context,
                    entity_id=f"{search_query}-{product_id}",
                    feature_type="search_product",
                )

                if features:
                    results[f"{search_query}-{product_id}"] = features

            return results
        except Exception as e:
            logger.error(
                f"Failed to compute search-product features from events: {str(e)}"
            )
            return {}

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from behavioral event"""
        try:
            event_data = event.get("eventData")
            if event_data and isinstance(event_data, dict):
                return event_data.get("productId") or event_data.get("product_id")
            return None
        except Exception:
            return None

    def _extract_search_query_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract search query from search event"""
        try:
            event_data = event.get("eventData")
            logger.info(f"🔍 Extracting search query from eventData: {event_data}")
            if event_data and isinstance(event_data, dict):
                # Check for searchResult.query first (Shopify format)
                if "searchResult" in event_data and isinstance(
                    event_data["searchResult"], dict
                ):
                    query = event_data["searchResult"].get("query")
                    logger.info(f"🔍 Found searchResult.query: {query}")
                    if query:
                        return query

                # Check for direct query field in eventData
                query = event_data.get("query")
                if query:
                    logger.info(f"🔍 Found direct query in eventData: {query}")
                    return query

                # Fallback to other possible query fields
                query = (
                    event_data.get("searchQuery")
                    or event_data.get("q")
                    or event_data.get("search_term")
                    or event_data.get("searchTerm")
                )
                logger.info(f"🔍 Fallback query extraction: {query}")
                return query
            return None
        except Exception as e:
            logger.error(f"🔍 Error extracting search query: {e}")
            return None

    def _extract_product_id_from_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract product ID from various event data structures"""
        try:
            if not isinstance(event_data, dict):
                return None

            # Check for direct product ID
            if "product" in event_data and isinstance(event_data["product"], dict):
                product_id = event_data["product"].get("id")
                if product_id and "Product" in product_id:
                    return product_id

            # Check for productVariant (product_viewed events)
            if "productVariant" in event_data and isinstance(
                event_data["productVariant"], dict
            ):
                variant_id = event_data["productVariant"].get("id")
                if variant_id:
                    return self._convert_variant_to_product_id(variant_id)

            # Check for cartLine.merchandise (cart events)
            if "cartLine" in event_data and isinstance(event_data["cartLine"], dict):
                merchandise = event_data["cartLine"].get("merchandise", {})
                if isinstance(merchandise, dict):
                    variant_id = merchandise.get("id")
                    if variant_id:
                        return self._convert_variant_to_product_id(variant_id)

            # Check for merchandise (direct cart events)
            if "merchandise" in event_data and isinstance(
                event_data["merchandise"], dict
            ):
                variant_id = event_data["merchandise"].get("id")
                if variant_id:
                    return self._convert_variant_to_product_id(variant_id)

            # Check for checkout.lineItems (checkout events)
            if "checkout" in event_data and isinstance(event_data["checkout"], dict):
                checkout = event_data["checkout"]
                if "lineItems" in checkout and isinstance(checkout["lineItems"], list):
                    # Get the first line item's product ID
                    for line_item in checkout["lineItems"]:
                        if isinstance(line_item, dict) and "variant" in line_item:
                            variant = line_item["variant"]
                            if isinstance(variant, dict) and "id" in variant:
                                variant_id = variant["id"]
                                if variant_id:
                                    return self._convert_variant_to_product_id(variant_id)

            # Check for cart.lines (cart events)
            if "cart" in event_data and isinstance(event_data["cart"], dict):
                cart = event_data["cart"]
                if "lines" in cart and isinstance(cart["lines"], list):
                    # Get the first line's product ID
                    for line in cart["lines"]:
                        if isinstance(line, dict) and "merchandise" in line:
                            merchandise = line["merchandise"]
                            if isinstance(merchandise, dict) and "id" in merchandise:
                                variant_id = merchandise["id"]
                                if variant_id:
                                    return self._convert_variant_to_product_id(variant_id)

            # Check for collection.productVariants (collection events)
            if "collection" in event_data and isinstance(event_data["collection"], dict):
                collection = event_data["collection"]
                if "productVariants" in collection and isinstance(collection["productVariants"], list):
                    # Get the first product variant's product ID
                    for variant in collection["productVariants"]:
                        if isinstance(variant, dict) and "id" in variant:
                            variant_id = variant["id"]
                            if variant_id:
                                return self._convert_variant_to_product_id(variant_id)

            return None
        except Exception as e:
            logger.error(f"Failed to extract product ID: {e}")
            return None

    def _convert_variant_to_product_id(self, variant_id: str) -> Optional[str]:
        """Convert ProductVariant ID to Product ID"""
        try:
            if "ProductVariant" in variant_id:
                variant_num = variant_id.split("/")[-1]
                # Convert variant number to product number
                # Variant 2001 -> Product 1001, Variant 2002 -> Product 1002, etc.
                product_num = str(int(variant_num) - 1000)
                return f"gid://shopify/Product/{product_num}"
            return variant_id
        except Exception:
            return None
