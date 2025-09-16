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
                    # Get product ID mapping from context if available
                    product_id_mapping = context.get("product_id_mapping")

                    # Find the specific product data for this entity
                    product_data = {}
                    products_list = context.get("product_data", [])
                    current_product_id = entity.get("productId", "")

                    # Find the matching product in the products list
                    for product in products_list:
                        if product.get("productId") == current_product_id:
                            product_data = product
                            break

                    # Create a new context with the specific product data
                    product_context = context.copy()
                    product_context["product_data"] = product_data

                    features = await self._compute_feature_safely(
                        generator,
                        context.get("shop", {}).get("id", ""),
                        entity.get("productId", ""),
                        product_context,
                        entity_id=entity_id,
                        feature_type=feature_type,
                        product_id_mapping=product_id_mapping,
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
            entity_type: Type of entity ('products', 'customers', 'orders', 'collections', 'behavioral_events', 'user_interactions', 'user_sessions', 'purchase_attributions')
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
                    elif entity_type == "user_interactions":
                        chunk = await self.repository.get_user_interactions_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "user_sessions":
                        chunk = await self.repository.get_user_sessions_batch_since(
                            shop_id, since_timestamp, current_chunk_size, offset
                        )
                    elif entity_type == "purchase_attributions":
                        chunk = (
                            await self.repository.get_purchase_attributions_batch_since(
                                shop_id, since_timestamp, current_chunk_size, offset
                            )
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
                    elif entity_type == "user_interactions":
                        chunk = await self.repository.get_user_interactions_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "user_sessions":
                        chunk = await self.repository.get_user_sessions_batch(
                            shop_id, current_chunk_size, offset
                        )
                    elif entity_type == "purchase_attributions":
                        chunk = await self.repository.get_purchase_attributions_batch(
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

                # If we got fewer entities than requested, we've reached the end
                if len(chunk) < current_chunk_size:
                    break

            except Exception as e:
                logger.error(
                    f"Failed to load chunk of {entity_type} at offset {offset}: {str(e)}"
                )
                break

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
        # NEW: Unified analytics data
        user_interactions: Optional[List[Dict[str, Any]]] = None,
        user_sessions: Optional[List[Dict[str, Any]]] = None,
        purchase_attributions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute customer behavior features"""
        try:
            results = {}

            for customer in customers:
                # Filter events for this customer
                customer_id = customer.get("customerId", "")
                customer_events = []

                for event in behavioral_events or []:
                    event_customer_id = event.get("customerId", "")
                    # Customer IDs are already normalized at data ingestion level
                    if event_customer_id == customer_id:
                        customer_events.append(event)

                # NEW: Filter unified analytics data for this customer
                customer_interactions = []
                for interaction in user_interactions or []:
                    if interaction.get("customerId") == customer_id:
                        customer_interactions.append(interaction)

                customer_sessions = []
                for session in user_sessions or []:
                    if session.get("customerId") == customer_id:
                        customer_sessions.append(session)

                customer_attributions = []
                for attribution in purchase_attributions or []:
                    if attribution.get("customerId") == customer_id:
                        customer_attributions.append(attribution)

                # Build enhanced context with unified analytics data
                context = self._build_base_context(
                    shop,
                    behavioral_events=customer_events,
                    # NEW: Add unified analytics data to context
                    user_interactions=customer_interactions,
                    user_sessions=customer_sessions,
                    purchase_attributions=customer_attributions,
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

            # Customer IDs are already normalized at data ingestion level

            event_time_str = event.get("timestamp")

            # Parse event time to datetime object
            event_time = None
            if event_time_str:
                try:
                    if isinstance(event_time_str, str):
                        event_time = datetime.fromisoformat(
                            event_time_str.replace("Z", "+00:00")
                        )
                    elif isinstance(event_time_str, datetime):
                        event_time = event_time_str
                except:
                    event_time = None

            # Check if we need to start a new session for this customer
            should_start_new_session = True

            if customer_id in current_sessions:
                current_session_id = current_sessions[customer_id]
                last_event = (
                    sessions[current_session_id]["events"][-1]
                    if sessions[current_session_id]["events"]
                    else None
                )

                last_event_time = None
                if last_event:
                    last_event_time_str = last_event.get("timestamp")
                    if last_event_time_str:
                        try:
                            if isinstance(last_event_time_str, str):
                                last_event_time = datetime.fromisoformat(
                                    last_event_time_str.replace("Z", "+00:00")
                                )
                            elif isinstance(last_event_time_str, datetime):
                                last_event_time = last_event_time_str
                        except:
                            last_event_time = None

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

                # NEW: Load unified analytics data
                user_interactions = await self.process_entities_in_chunks(
                    shop_id,
                    "user_interactions",
                    batch_size * 3,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                user_sessions = await self.process_entities_in_chunks(
                    shop_id,
                    "user_sessions",
                    batch_size,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )
                purchase_attributions = await self.process_entities_in_chunks(
                    shop_id,
                    "purchase_attributions",
                    batch_size,
                    chunk_size=100,
                    incremental=True,
                    since_timestamp=last_computation_time,
                )

                # If no recent data, skip processing
                if not any(
                    [
                        products,
                        customers,
                        orders,
                        collections,
                        behavioral_events,
                        user_interactions,
                        user_sessions,
                        purchase_attributions,
                    ]
                ):

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

                # NEW: Load unified analytics data for full processing
                user_interactions = await self.process_entities_in_chunks(
                    shop_id, "user_interactions", batch_size * 3, chunk_size=100
                )
                user_sessions = await self.process_entities_in_chunks(
                    shop_id, "user_sessions", batch_size, chunk_size=100
                )
                purchase_attributions = await self.process_entities_in_chunks(
                    shop_id, "purchase_attributions", batch_size, chunk_size=100
                )

            # Compute all features using enhanced method with unified analytics data
            all_features = await self.compute_all_features_for_shop(
                shop=shop_data,
                products=products,
                customers=customers,
                orders=orders,
                collections=collections,
                behavioral_events=behavioral_events,
                # NEW: Pass unified analytics data
                user_interactions=user_interactions,
                user_sessions=user_sessions,
                purchase_attributions=purchase_attributions,
            )

            # Save all features to database with parallel processing
            save_results = await self._save_all_features_with_parallel_processing(
                shop_id, all_features
            )

            # Trigger unified Gorse sync after successful feature computation
            await self._trigger_gorse_sync(shop_id, save_results)

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
                pass
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
                    # NEW: Include unified analytics data counts
                    "user_interactions": len(user_interactions),
                    "user_sessions": len(user_sessions),
                    "purchase_attributions": len(purchase_attributions),
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
        # NEW: Unified analytics data
        user_interactions: Optional[List[Dict[str, Any]]] = None,
        user_sessions: Optional[List[Dict[str, Any]]] = None,
        purchase_attributions: Optional[List[Dict[str, Any]]] = None,
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
            # NEW: Prepare unified analytics data
            user_interactions = user_interactions or []
            user_sessions = user_sessions or []
            purchase_attributions = purchase_attributions or []

            # 1. Product Features
            # Create product ID mapping for product features
            product_id_mapping = self._create_product_id_mapping(
                behavioral_events, products
            )
            product_context = self._build_base_context(
                shop,
                product_data=products or [],
                orders=orders or [],
                collections=collections or [],
                behavioral_events=behavioral_events or [],
                product_id_mapping=product_id_mapping,
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
            user_context = self._build_base_context(
                shop, orders=orders or [], events=behavioral_events or []
            )
            user_features = await self._process_entities_batch(
                customers, self.user_generator, user_context, "customerId", "user"
            )
            all_features["users"] = user_features

            # 3. Collection Features
            collection_features = await self.compute_all_collection_features(
                collections, shop, products, behavioral_events, orders
            )
            all_features["collections"] = collection_features

            # 4. Customer Behavior Features (Enhanced with unified analytics)
            behavior_features = await self.compute_all_customer_behavior_features(
                customers,
                shop,
                behavioral_events,
                # NEW: Pass unified analytics data
                user_interactions=user_interactions,
                user_sessions=user_sessions,
                purchase_attributions=purchase_attributions,
            )
            all_features["customer_behaviors"] = behavior_features

            # 5. Session Features
            session_features = await self.generate_session_features_from_events(
                behavioral_events, shop, orders
            )
            all_features["sessions"] = session_features

            # 6. Interaction Features (sample of customer-product pairs)
            interaction_context = self._build_base_context(
                shop,
                orders=orders or [],
                behavioral_events=behavioral_events or [],
            )

            # Create variant ID to product ID mapping from products data
            variant_to_product_map = {}
            for product in products or []:
                product_id = product.get("productId")
                if product_id:
                    variants = product.get("variants", [])
                    for variant in variants:
                        if isinstance(variant, dict) and "id" in variant:
                            variant_id = variant["id"]
                            # Variant IDs are already normalized at data ingestion level
                            variant_to_product_map[variant_id] = product_id

            # Find customer-product pairs that have interactions
            interaction_pairs = set()

            # Create product ID mapping from behavioral events to ProductData
            product_id_mapping = self._create_product_id_mapping(
                behavioral_events, products
            )

            # From behavioral events
            for event in behavioral_events:
                if event.get("customerId") and "eventData" in event:
                    event_product_id = self._extract_product_id_from_event(event)
                    if event_product_id:
                        customer_id = event.get("customerId")
                        # IDs are already normalized at data ingestion level

                        # Map behavioral event product ID to ProductData product ID
                        mapped_product_id = product_id_mapping.get(
                            event_product_id, event_product_id
                        )

                        # Only add if both IDs are valid
                        if customer_id and mapped_product_id:
                            interaction_pairs.add((customer_id, mapped_product_id))

            # From orders
            for order in orders:
                if order.get("customerId"):
                    customer_id = order.get("customerId")
                    # Customer IDs are already normalized at data ingestion level
                    for line_item in order.get("lineItems", []):
                        # Extract product ID from line item structure using variant mapping
                        product_id = None

                        # Try to get product ID from variant mapping
                        if "variant" in line_item and isinstance(
                            line_item["variant"], dict
                        ):
                            variant_id = line_item["variant"].get("id")
                            if variant_id and variant_id in variant_to_product_map:
                                product_id = variant_to_product_map[variant_id]

                        # Fallback: try direct product_id field
                        if not product_id and "product_id" in line_item:
                            product_id = line_item.get("product_id")

                        # Fallback: try variant.product.id structure
                        if (
                            not product_id
                            and "variant" in line_item
                            and isinstance(line_item["variant"], dict)
                        ):
                            product = line_item["variant"].get("product", {})
                            if isinstance(product, dict):
                                product_id = product.get("id")

                        # Product IDs are already normalized at data ingestion level
                        # Only add if both IDs are valid
                        if customer_id and product_id:
                            interaction_pairs.add((customer_id, product_id))
            # Generate features for each interaction pair
            interaction_features = {}
            for customer_id, product_id in interaction_pairs:
                try:
                    # Product IDs are already normalized at data ingestion level
                    full_product_id = product_id
                    features = await self.interaction_generator.generate_features(
                        shop["id"],
                        customer_id,
                        full_product_id,
                        interaction_context,
                        product_id_mapping,
                    )
                    key = f"{customer_id}_{product_id}"
                    interaction_features[key] = features

                except Exception as e:
                    logger.error(
                        f"Failed to generate interaction features for {customer_id}-{product_id}: {e}"
                    )

            all_features["interactions"] = interaction_features

            # 7. Product Pair Features (top product pairs)
            product_pair_context = self._build_base_context(
                shop,
                orders=orders or [],
                behavioral_events=behavioral_events or [],
            )
            # Add variant-to-product mapping for product pair analysis
            product_pair_context["variant_to_product_map"] = variant_to_product_map

            # Use the variant-to-product mapping created earlier

            # Find product pairs that co-occur in orders
            product_pairs = set()
            for order in orders:
                order_products = []
                for line_item in order.get("lineItems", []):
                    # Extract product ID from line item structure
                    product_id = None

                    # Try different possible structures
                    if "product_id" in line_item:
                        product_id = line_item.get("product_id")
                    elif "variant" in line_item and isinstance(
                        line_item["variant"], dict
                    ):
                        variant = line_item["variant"]
                        # Check if variant has product field
                        if "product" in variant and isinstance(
                            variant["product"], dict
                        ):
                            product_id = variant["product"].get("id")
                        # If no product field, try to map variant ID to product ID
                        elif "id" in variant:
                            variant_id = variant["id"]
                            if variant_id in variant_to_product_map:
                                product_id = variant_to_product_map[variant_id]

                    # Product IDs are already normalized at data ingestion level
                    if product_id:
                        order_products.append(product_id)

                # Create pairs from products in the same order
                for i in range(len(order_products)):
                    for j in range(i + 1, len(order_products)):
                        pair = tuple(sorted([order_products[i], order_products[j]]))
                        product_pairs.add(pair)

            # Generate features for each product pair
            product_pair_features = {}
            for product_id1, product_id2 in product_pairs:
                try:
                    features = await self.product_pair_generator.generate_features(
                        shop["id"], product_id1, product_id2, product_pair_context
                    )
                    key = f"{product_id1}_{product_id2}"
                    product_pair_features[key] = features
                except Exception as e:
                    logger.error(
                        f"Failed to generate product pair features for {product_id1}-{product_id2}: {e}"
                    )

            all_features["product_pairs"] = product_pair_features

            # 8. Search Product Features (from search events)
            search_context = self._build_base_context(
                shop,
                behavioral_events=behavioral_events or [],
            )

            # Find search-to-product correlations
            search_product_pairs = set()

            # Get all search events and product view events
            search_events = []
            product_view_events = []

            for event in behavioral_events:
                if event.get("eventType") == "search_submitted":
                    search_events.append(event)
                elif event.get("eventType") == "product_viewed":
                    product_view_events.append(event)

            # Sort all events by timestamp for time-based correlation
            all_events = search_events + product_view_events
            all_events.sort(key=lambda x: x.get("timestamp", ""))

            # Find search events followed by product views within 24 hours
            for i, event in enumerate(all_events):
                if event.get("eventType") == "search_submitted":
                    search_query = self._extract_search_query_from_event(event)
                    if search_query:
                        search_time = event.get("timestamp")
                        search_customer = event.get("customerId") or "anonymous"

                        # Look for product views within 24 hours after search
                        for j in range(i + 1, len(all_events)):
                            later_event = all_events[j]
                            if later_event.get("eventType") == "product_viewed":
                                later_time = later_event.get("timestamp")
                                later_customer = (
                                    later_event.get("customerId") or "anonymous"
                                )

                                # Check time difference (within 24 hours)
                                if search_time and later_time:
                                    try:
                                        from datetime import datetime

                                        search_dt = datetime.fromisoformat(
                                            search_time.replace("Z", "+00:00")
                                        )
                                        later_dt = datetime.fromisoformat(
                                            later_time.replace("Z", "+00:00")
                                        )
                                        time_diff = (
                                            later_dt - search_dt
                                        ).total_seconds()

                                        # Only consider if within 24 hours and same customer (or both anonymous)
                                        if 0 <= time_diff < 86400 and (
                                            search_customer == later_customer
                                            or (
                                                search_customer == "anonymous"
                                                and later_customer == "anonymous"
                                            )
                                        ):
                                            product_id = (
                                                self._extract_product_id_from_event(
                                                    later_event
                                                )
                                            )
                                            if product_id:
                                                search_product_pairs.add(
                                                    (search_query, product_id)
                                                )
                                            else:
                                                continue
                                    except Exception as e:
                                        logger.debug(f"Error parsing timestamps: {e}")
                                        continue

            # Generate features for each search-product pair
            search_product_features = {}
            for search_query, product_id in search_product_pairs:
                try:
                    search_product_data = {
                        "searchQuery": search_query,
                        "productId": product_id,
                    }
                    features = await self.search_product_generator.generate_features(
                        search_product_data, search_context
                    )
                    key = f"{search_query}_{product_id}"
                    search_product_features[key] = features
                except Exception as e:
                    logger.error(
                        f"Failed to generate search product features for {search_query}-{product_id}: {e}"
                    )

            all_features["search_products"] = search_product_features

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
                        if "_" in entity_id or "-" in entity_id:
                            if feature_type == "interaction":
                                # Handle both _ and - separators
                                separator = "_" if "_" in entity_id else "-"
                                customer_id, product_id = entity_id.split(separator, 1)
                                # For interaction, we need to pass the feature_data directly
                                # The shop_id, customer_id, product_id are already in feature_data
                                batch_data.append(feature_data)
                            elif feature_type == "product_pair":
                                # Handle both _ and - separators
                                separator = "_" if "_" in entity_id else "-"
                                product_id1, product_id2 = entity_id.split(separator, 1)
                                # For product_pair, we need to pass the feature_data directly
                                # The shop_id, product_id1, product_id2 are already in feature_data
                                batch_data.append(feature_data)
                            elif feature_type == "search_product":
                                # Handle both _ and - separators
                                separator = "_" if "_" in entity_id else "-"
                                search_query, product_id = entity_id.split(separator, 1)
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

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from event data (IDs are already normalized)"""
        try:
            event_type = event.get("eventType")
            event_data = event.get("eventData", {})

            # Handle string eventData
            if isinstance(event_data, str):
                try:
                    import json

                    event_data = json.loads(event_data)
                except:
                    return None

            if event_type == "product_viewed":
                # Handle nested data structure: eventData.data.productVariant.product
                if "data" in event_data:
                    product_variant = event_data.get("data", {}).get(
                        "productVariant", {}
                    )
                else:
                    product_variant = event_data.get("productVariant", {})
                product = product_variant.get("product", {})
                return product.get("id", "")

            elif event_type == "product_added_to_cart":
                # Handle nested data structure: eventData.data.cartLine.merchandise.product
                if "data" in event_data:
                    cart_line = event_data.get("data", {}).get("cartLine", {})
                else:
                    cart_line = event_data.get("cartLine", {})
                merchandise = cart_line.get("merchandise", {})
                product = merchandise.get("product", {})
                return product.get("id", "")

            elif event_type == "product_removed_from_cart":
                cart_line = event_data.get("data", {}).get(
                    "cartLine", {}
                ) or event_data.get("cartLine", {})
                merchandise = cart_line.get("merchandise", {})
                product = merchandise.get("product", {})
                return product.get("id", "")

            return None

        except Exception as e:
            logger.error(f"Error extracting product ID from event: {str(e)}")
            return None

    def _create_product_id_mapping(
        self, behavioral_events: List[Dict[str, Any]], products: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Create mapping between behavioral event product IDs and ProductData product IDs (IDs are already normalized)"""
        mapping = {}

        # Create a mapping based on product titles
        # Since IDs are already normalized, we can directly use them
        for event in behavioral_events:
            if event.get("eventType") in [
                "product_viewed",
                "product_added_to_cart",
                "checkout_completed",
            ]:
                event_data = event.get("eventData", {})

                # Handle string eventData
                if isinstance(event_data, str):
                    try:
                        import json

                        event_data = json.loads(event_data)
                    except:
                        continue

                # Extract product information from different event types
                product_info = None

                if event.get("eventType") == "product_viewed":
                    # Handle nested data structure: eventData.data.productVariant.product
                    if "data" in event_data:
                        product_variant = event_data.get("data", {}).get(
                            "productVariant", {}
                        )
                    else:
                        product_variant = event_data.get("productVariant", {})
                    product_info = product_variant.get("product", {})

                elif event.get("eventType") == "product_added_to_cart":
                    # Handle nested data structure: eventData.data.cartLine.merchandise.product
                    if "data" in event_data:
                        cart_line = event_data.get("data", {}).get("cartLine", {})
                    else:
                        cart_line = event_data.get("cartLine", {})
                    merchandise = cart_line.get("merchandise", {})
                    product_info = merchandise.get("product", {})

                elif event.get("eventType") == "checkout_completed":
                    # Handle nested data structure: eventData.data.checkout.lineItems
                    if "data" in event_data:
                        checkout = event_data.get("data", {}).get("checkout", {})
                    else:
                        checkout = event_data.get("checkout", {})
                    line_items = checkout.get("lineItems", [])
                    for item in line_items:
                        variant = item.get("variant", {})
                        product_info = variant.get("product", {})
                        if product_info:
                            break

                if product_info:
                    # IDs are already normalized, so we can use them directly
                    event_product_id = product_info.get("id", "")
                    product_title = product_info.get("title", "")

                    if event_product_id and product_title:
                        # Find matching product in ProductData by title
                        for product in products:
                            if product.get("title") == product_title:
                                mapping[event_product_id] = product.get("productId", "")
                                break

        return mapping

    def _extract_search_query_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract search query from search event"""
        try:
            event_data = event.get("eventData")
            if event_data and isinstance(event_data, dict):
                # Check for searchResult.query first (Shopify format)
                if "searchResult" in event_data and isinstance(
                    event_data["searchResult"], dict
                ):
                    query = event_data["searchResult"].get("query")
                    if query:
                        return query

                # Check for direct query field in eventData
                query = event_data.get("query")
                if query:
                    return query

                # Fallback to other possible query fields
                query = (
                    event_data.get("searchQuery")
                    or event_data.get("q")
                    or event_data.get("search_term")
                    or event_data.get("searchTerm")
                )
                return query
            return None
        except Exception as e:
            logger.error(f"Error extracting search query: {e}")
            return None

    def _convert_variant_to_product_id(self, variant_id: str) -> Optional[str]:
        """Convert ProductVariant ID to Product ID"""
        try:
            if "ProductVariant" in variant_id:
                variant_num = variant_id.split("/")[-1]
                # Convert variant number to product number
                # Variant 2001 -> Product 1001, Variant 2002 -> Product 1002, etc.
                product_num = str(int(variant_num) - 1000)
                return product_num
            return variant_id
        except Exception:
            return None

    async def _trigger_gorse_sync(self, shop_id: str, save_results: Dict[str, Any]):
        """Trigger unified Gorse sync after successful feature computation"""
        try:
            from app.domains.ml.services.unified_gorse_service import (
                UnifiedGorseService,
            )

            # Initialize unified Gorse service
            gorse_service = UnifiedGorseService()

            logger.info(
                f"Starting unified Gorse sync after feature computation",
                shop_id=shop_id,
                feature_results=save_results,
            )

            # Run unified sync and training with incremental sync since we just computed features
            result = await gorse_service.sync_and_train(
                shop_id=shop_id,
                sync_type="incremental",
                since_hours=0,  # Only sync data from last hour since we just computed features
                trigger_source="feature_computation",
            )

            logger.info(
                f"Unified Gorse sync completed after feature computation",
                shop_id=shop_id,
                gorse_success=result.get("success", False),
                gorse_job_id=result.get("job_id"),
                training_triggered=result.get("training_status", {}).get(
                    "triggered", False
                ),
                sync_results=result.get("sync_results", {}),
            )

        except Exception as e:
            logger.error(
                f"Failed to trigger unified Gorse sync after feature computation: {str(e)}",
                shop_id=shop_id,
            )
            # Don't raise the exception - feature computation succeeded, Gorse sync failure shouldn't fail the whole job
