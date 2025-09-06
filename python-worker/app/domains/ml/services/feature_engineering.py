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

from .feature_pipeline import FeaturePipeline, IFeaturePipeline
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
        pipeline: Optional[IFeaturePipeline] = None,
        repository: Optional[IFeatureRepository] = None,
    ):
        # Initialize components
        self.repository = repository or FeatureRepository()
        self.pipeline = pipeline or FeaturePipeline(self.repository)

        # Initialize feature generators for individual feature computation
        self.product_generator = ProductFeatureGenerator()
        self.user_generator = UserFeatureGenerator()
        self.interaction_generator = InteractionFeatureGenerator()
        self.collection_generator = CollectionFeatureGenerator()
        self.session_generator = SessionFeatureGenerator()
        self.customer_behavior_generator = CustomerBehaviorFeatureGenerator()
        self.search_product_generator = SearchProductFeatureGenerator()
        self.product_pair_generator = ProductPairFeatureGenerator()

        # Feature computation settings
        self.max_features_per_entity = 100
        self.feature_quality_threshold = 0.7

        # Feature schemas for validation
        self.feature_schemas = self._initialize_feature_schemas()

        # Feature importance weights
        self.feature_importance_weights = self._initialize_feature_importance()

    async def compute_product_features(
        self,
        product: ShopifyProduct,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a product using the product generator"""
        try:
            context = {
                "shop": shop,
                "orders": orders or [],
                "collections": collections or [],
            }
            return await self.product_generator.generate_features(product, context)
        except Exception as e:
            logger.error(
                f"Failed to compute product features for {product.id}: {str(e)}"
            )
            return {}

    async def compute_user_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a user/customer using the user generator"""
        try:
            context = {
                "shop": shop,
                "orders": orders or [],
                "events": events or [],
            }
            return await self.user_generator.generate_features(customer, context)
        except Exception as e:
            logger.error(f"Failed to compute user features for {customer.id}: {str(e)}")
            return {}

    async def compute_interaction_features(
        self,
        customer: ShopifyCustomer,
        product: ShopifyProduct,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for customer-product interactions using the interaction generator"""
        try:
            # Create interaction data structure
            interaction_data = {
                "customerId": customer.id,
                "productId": product.id,
            }
            context = {
                "shop": shop,
                "orders": orders or [],
                "events": events or [],
            }
            return await self.interaction_generator.generate_features(
                interaction_data, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute interaction features for {customer.id}-{product.id}: {str(e)}"
            )
            return {}

    async def compute_collection_features(
        self,
        collection: ShopifyCollection,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
        order_data: Optional[List[ShopifyOrder]] = None,
        shop_analytics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a collection using the collection generator"""
        try:
            context = {
                "shop": shop,
                "products": products or [],
                "behavioral_events": behavioral_events or [],
                "order_data": order_data or [],
                "shop_analytics": shop_analytics or {},
            }
            return await self.collection_generator.generate_features(
                collection, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute collection features for {collection.id}: {str(e)}"
            )
            return {}

    async def compute_session_features(
        self,
        session_data: Dict[str, Any],
        shop: ShopifyShop,
        order_data: Optional[List[ShopifyOrder]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a session using the session generator"""
        try:
            context = {
                "shop": shop,
                "order_data": order_data or [],
            }
            return await self.session_generator.generate_features(session_data, context)
        except Exception as e:
            logger.error(
                f"Failed to compute session features for {session_data.get('sessionId', 'unknown')}: {str(e)}"
            )
            return {}

    async def compute_customer_behavior_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for customer behavior using the customer behavior generator"""
        try:
            context = {
                "shop": shop,
                "behavioral_events": behavioral_events or [],
            }
            return await self.customer_behavior_generator.generate_features(
                customer, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute customer behavior features for {customer.id}: {str(e)}"
            )
            return {}

    async def compute_search_product_features(
        self,
        search_query: str,
        product_id: str,
        shop: ShopifyShop,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for search-product combination using the search product generator"""
        try:
            search_product_data = {
                "searchQuery": search_query,
                "productId": product_id,
            }
            context = {
                "shop": shop,
                "behavioral_events": behavioral_events or [],
            }
            return await self.search_product_generator.generate_features(
                search_product_data, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute search-product features for '{search_query}' + {product_id}: {str(e)}"
            )
            return {}

    async def compute_product_pair_features(
        self,
        product_id1: str,
        product_id2: str,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for product pairs using the product pair generator"""
        try:
            context = {
                "orders": orders or [],
                "behavioral_events": behavioral_events or [],
            }
            return await self.product_pair_generator.generate_features(
                shop.id, product_id1, product_id2, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute product pair features for {product_id1}-{product_id2}: {str(e)}"
            )
            return {}

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
                    features = await self.product_generator.generate_features(product, context)
                    results[product.id] = features
                except Exception as e:
                    logger.error(f"Failed to compute features for product {product.id}: {str(e)}")
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
                    features = await self.user_generator.generate_features(customer, context)
                    results[customer.id] = features
                except Exception as e:
                    logger.error(f"Failed to compute user features for {customer.id}: {str(e)}")
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
        shop_analytics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch compute features for multiple collections"""
        try:
            results = {}
            context = {
                "shop": shop,
                "products": products or [],
                "behavioral_events": behavioral_events or [],
                "order_data": order_data or [],
                "shop_analytics": shop_analytics or {},
            }
            
            for collection in collections:
                try:
                    features = await self.collection_generator.generate_features(collection, context)
                    results[collection.id] = features
                except Exception as e:
                    logger.error(f"Failed to compute collection features for {collection.id}: {str(e)}")
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
                        event for event in (behavioral_events or [])
                        if event.customerId == customer.id
                    ]
                    
                    context = {
                        "shop": shop,
                        "behavioral_events": customer_events,
                    }
                    
                    features = await self.customer_behavior_generator.generate_features(customer, context)
                    results[customer.id] = features
                except Exception as e:
                    logger.error(f"Failed to compute customer behavior features for {customer.id}: {str(e)}")
                    results[customer.id] = {}
                    
            return results
        except Exception as e:
            logger.error(f"Failed to batch compute customer behavior features: {str(e)}")
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
                    
                    features = await self.session_generator.generate_features(session_data, context)
                    results[session_id] = features
                except Exception as e:
                    logger.error(f"Failed to compute session features for {session_id}: {str(e)}")
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
        sorted_events = sorted(events, key=lambda e: e.occurredAt if e.occurredAt else datetime.min)
        
        current_sessions = {}  # customer_id -> current_session_id
        
        for event in sorted_events:
            customer_id = event.customerId or "anonymous"
            event_time = event.occurredAt
            
            # Check if we need to start a new session for this customer
            should_start_new_session = True
            
            if customer_id in current_sessions:
                current_session_id = current_sessions[customer_id]
                last_event_time = sessions[current_session_id]["events"][-1].occurredAt if sessions[current_session_id]["events"] else None
                
                if last_event_time and event_time:
                    time_diff = (event_time - last_event_time).total_seconds() / 60
                    if time_diff <= session_timeout_minutes:
                        should_start_new_session = False
            
            if should_start_new_session:
                # Create new session
                import uuid
                session_id = f"{customer_id}_{event_time.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}" if event_time else f"{customer_id}_{str(uuid.uuid4())[:8]}"
                current_sessions[customer_id] = session_id
                sessions[session_id]["customerId"] = customer_id if customer_id != "anonymous" else None
            
            # Add event to current session
            current_session_id = current_sessions[customer_id]
            sessions[current_session_id]["events"].append(event)
        
        return dict(sessions)

    async def compute_all_features_for_shop(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
        shop_analytics: Optional[Dict[str, Any]] = None,
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
            shop_analytics = shop_analytics or {}
            
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
                collections, shop, products, behavioral_events, orders, shop_analytics
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
            search_product_features = await self._compute_search_product_features_from_events(
                behavioral_events, shop
            )
            all_features["search_products"] = search_product_features
            
            logger.info(f"Completed comprehensive feature computation for shop {shop.id}")
            return all_features
            
        except Exception as e:
            logger.error(f"Failed to compute comprehensive shop features: {str(e)}")
            return {}

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
                        if hasattr(line_item, 'product_id'):
                            interaction_pairs.add((order.customer_id, line_item.product_id))
            
            # From behavioral events
            for event in behavioral_events:
                if event.customerId and hasattr(event, 'eventData'):
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
                    logger.error(f"Failed to compute interaction features for {customer_id}-{product_id}: {str(e)}")
                    
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
                product_ids = [item.product_id for item in order.line_items if hasattr(item, 'product_id')]
                
                # Create pairs
                for i in range(len(product_ids)):
                    for j in range(i + 1, len(product_ids)):
                        pair = tuple(sorted([product_ids[i], product_ids[j]]))
                        co_occurrence_counts[pair] = co_occurrence_counts.get(pair, 0) + 1
            
            # Get top pairs (limit to prevent excessive computation)
            top_pairs = sorted(co_occurrence_counts.items(), key=lambda x: x[1], reverse=True)[:100]
            
            for (product_id1, product_id2), count in top_pairs:
                try:
                    features = await self.compute_product_pair_features(
                        product_id1, product_id2, shop, orders, behavioral_events
                    )
                    results[f"{product_id1}-{product_id2}"] = features
                except Exception as e:
                    logger.error(f"Failed to compute product pair features for {product_id1}-{product_id2}: {str(e)}")
                    
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
                if event.eventType == "search_submitted" and hasattr(event, 'eventData'):
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
                    logger.error(f"Failed to compute search-product features for {search_query}-{product_id}: {str(e)}")
                    
            return results
        except Exception as e:
            logger.error(f"Failed to compute search-product features from events: {str(e)}")
            return {}

    def _extract_product_id_from_event(self, event: BehavioralEvent) -> Optional[str]:
        """Extract product ID from behavioral event"""
        try:
            if hasattr(event, 'eventData') and event.eventData:
                if isinstance(event.eventData, dict):
                    return (event.eventData.get("productId") or 
                           event.eventData.get("product_id"))
            return None
        except Exception:
            return None

    def _extract_search_query_from_event(self, event: BehavioralEvent) -> Optional[str]:
        """Extract search query from search event"""
        try:
            if hasattr(event, 'eventData') and event.eventData:
                if isinstance(event.eventData, dict):
                    return (event.eventData.get("query") or 
                           event.eventData.get("searchQuery") or
                           event.eventData.get("q"))
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

    async def validate_features(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, Any]:
        """Validate computed features"""
        try:
            schema = await self.get_feature_schema(feature_type)
            validated_features = {}

            for key, value in features.items():
                if key in schema:
                    # Apply validation rules from schema
                    if schema[key].get("required", False) and value is None:
                        logger.warning(
                            f"Required feature {key} is missing for {feature_type}"
                        )
                        validated_features[key] = schema[key].get("default", 0)
                    else:
                        validated_features[key] = value
                else:
                    validated_features[key] = value

            return validated_features

        except Exception as e:
            logger.error(f"Failed to validate features for {feature_type}: {str(e)}")
            return features

    async def get_feature_schema(self, feature_type: str) -> Dict[str, Any]:
        """Get feature schema for a type"""
        return self.feature_schemas.get(feature_type, {})

    async def get_feature_importance(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, float]:
        """Get feature importance scores"""
        try:
            weights = self.feature_importance_weights.get(feature_type, {})
            importance_scores = {}

            for feature_name, feature_value in features.items():
                if feature_name in weights:
                    # Calculate importance based on weight and feature value
                    base_weight = weights[feature_name]
                    if isinstance(feature_value, (int, float)):
                        # Normalize feature value and apply weight
                        normalized_value = min(abs(feature_value) / 100, 1.0)
                        importance_scores[feature_name] = base_weight * normalized_value
                else:
                    importance_scores[feature_name] = base_weight

            return importance_scores

        except Exception as e:
            logger.error(
                f"Failed to get feature importance for {feature_type}: {str(e)}"
            )
            return {}

    async def normalize_features(
        self,
        features: Dict[str, Any],
        feature_type: str,
        normalization_method: str = "standard",
        shop_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize features for ML training using dataset-wide statistics"""
        try:
            # For proper normalization, we need dataset-wide statistics
            if not shop_id:
                logger.warning(
                    "Shop ID not provided for normalization, using identity normalization"
                )
                return features

            # Get dataset statistics for this shop and feature type
            dataset_stats = await self._get_dataset_statistics(shop_id, feature_type)

            normalized_features = {}

            for feature_name, feature_value in features.items():
                if (
                    isinstance(feature_value, (int, float))
                    and feature_value is not None
                ):
                    if normalization_method == "standard":
                        # Standard scaling (z-score): (value - mean) / std
                        mean = dataset_stats.get(feature_name, {}).get("mean", 0)
                        std = dataset_stats.get(feature_name, {}).get("std", 1)
                        if std > 0:
                            normalized_features[feature_name] = (
                                feature_value - mean
                            ) / std
                        else:
                            normalized_features[feature_name] = 0
                    elif normalization_method == "minmax":
                        # Min-max scaling: (value - min) / (max - min)
                        min_val = dataset_stats.get(feature_name, {}).get("min", 0)
                        max_val = dataset_stats.get(feature_name, {}).get("max", 1)
                        if max_val > min_val:
                            normalized_features[feature_name] = (
                                feature_value - min_val
                            ) / (max_val - min_val)
                        else:
                            normalized_features[feature_name] = 0
                    elif normalization_method == "robust":
                        # Robust scaling: (value - median) / IQR
                        median = dataset_stats.get(feature_name, {}).get("median", 0)
                        iqr = dataset_stats.get(feature_name, {}).get("iqr", 1)
                        if iqr > 0:
                            normalized_features[feature_name] = (
                                feature_value - median
                            ) / iqr
                        else:
                            normalized_features[feature_name] = 0
                    else:
                        normalized_features[feature_name] = feature_value
                else:
                    normalized_features[feature_name] = feature_value

            return normalized_features

        except Exception as e:
            logger.error(
                f"Failed to normalize features", feature_type=feature_type, error=str(e)
            )
            return features

    async def encode_categorical_features(
        self,
        features: Dict[str, Any],
        feature_type: str,
        encoding_method: str = "one_hot",
    ) -> Dict[str, Any]:
        """Encode categorical features"""
        try:
            encoded_features = {}

            for feature_name, feature_value in features.items():
                if isinstance(feature_value, str):
                    if encoding_method == "one_hot":
                        # Simple hash-based encoding (placeholder)
                        encoded_features[feature_name] = hash(feature_value) % 1000
                    elif encoding_method == "label":
                        # Label encoding (placeholder)
                        encoded_features[feature_name] = hash(feature_value) % 1000
                    else:
                        encoded_features[feature_name] = feature_value
                else:
                    encoded_features[feature_name] = feature_value

            return encoded_features

        except Exception as e:
            logger.error(
                f"Failed to encode categorical features for {feature_type}: {str(e)}"
            )
            return features

    async def compute_feature_statistics(
        self, features_list: List[Dict[str, Any]], feature_type: str
    ) -> Dict[str, Any]:
        """Compute statistics across multiple feature sets"""
        try:
            if not features_list:
                return {}

            # Collect all feature values by name
            feature_values = {}
            for features in features_list:
                for feature_name, feature_value in features.items():
                    if isinstance(feature_value, (int, float)):
                        if feature_name not in feature_values:
                            feature_values[feature_name] = []
                        feature_values[feature_name].append(feature_value)

            # Compute statistics for each feature
            statistics_result = {}
            for feature_name, values in feature_values.items():
                if values:
                    statistics_result[feature_name] = {
                        "mean": statistics.mean(values),
                        "std": statistics.stdev(values) if len(values) > 1 else 0,
                        "median": statistics.median(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values),
                    }

            return statistics_result

        except Exception as e:
            logger.error(
                f"Failed to compute feature statistics for {feature_type}: {str(e)}"
            )
            return {}

    # Pipeline methods - delegate to the pipeline
    async def run_feature_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 500, incremental: bool = True
    ) -> Dict[str, Any]:
        """Run complete feature engineering pipeline for a shop using batch processing"""
        return await self.pipeline.run_feature_pipeline_for_shop(
            shop_id, batch_size, incremental
        )

    # Helper methods (extracted from original service)
    def _initialize_feature_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Initialize feature schemas for validation"""
        return {
            "product": {
                "product_id": {"type": "string", "required": True},
                "title_length": {"type": "integer", "required": False, "default": 0},
                "price_tier": {"type": "string", "required": False, "default": "low"},
            },
            "customer": {
                "customer_id": {"type": "string", "required": True},
                "total_orders": {"type": "integer", "required": False, "default": 0},
                "total_spent": {"type": "float", "required": False, "default": 0},
            },
            # Add more schemas as needed
        }

    def _initialize_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Initialize feature importance weights"""
        return {
            "product": {
                "total_orders": 0.9,
                "avg_price": 0.8,
                "quality_score": 0.7,
                "variant_count": 0.6,
            },
            "customer": {
                "total_spent": 0.9,
                "total_orders": 0.8,
                "engagement_score": 0.7,
                "days_since_last_order": 0.6,
            },
            # Add more importance weights as needed
        }

    async def _get_dataset_statistics(
        self, shop_id: str, feature_type: str
    ) -> Dict[str, Dict[str, float]]:
        """Get dataset-wide statistics for normalization"""
        try:
            # This is a placeholder implementation
            # In a real implementation, you would query the database to get
            # statistics across all features of the given type for the shop

            logger.warning(
                f"Dataset statistics not implemented for {feature_type}, using identity normalization"
            )
            return {}

        except Exception as e:
            logger.error(f"Failed to get dataset statistics: {str(e)}")
            return {}

    # Cross-entity feature computation methods (extracted from original service)
    def _compute_product_customer_interactions(
        self,
        products: List[ShopifyProduct],
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
    ) -> Dict[str, Any]:
        """Compute product-customer interaction features"""
        # Implementation extracted from original service
        return {
            "total_interactions": len(orders),
            "unique_customers": len(
                set(o.customer_id for o in orders if o.customer_id)
            ),
            "unique_products": len(
                set(item.product_id for o in orders for item in o.line_items)
            ),
            "average_products_per_order": (
                sum(len(o.line_items) for o in orders) / len(orders) if orders else 0
            ),
        }

    def _compute_collection_performance_features_batch(
        self,
        collections: List[ShopifyCollection],
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
    ) -> Dict[str, Any]:
        """Compute collection performance features"""
        # Implementation extracted from original service
        return {
            "total_collections": len(collections),
            "avg_collection_size": (
                statistics.mean([c.products_count for c in collections])
                if collections
                else 0
            ),
        }

    def _compute_customer_segment_features(
        self,
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
        events: List[BehavioralEvent],
    ) -> Dict[str, Any]:
        """Compute customer segment features"""
        # Implementation extracted from original service
        return {
            "total_customers": len(customers),
            "high_value_customers": len([c for c in customers if c.total_spent > 1000]),
        }

    def _compute_product_category_features(
        self, products: List[ShopifyProduct], collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute product category features"""
        # Implementation extracted from original service
        return {
            "total_products": len(products),
            "unique_categories": len(
                set(p.product_type for p in products if p.product_type)
            ),
        }

    def _compute_time_series_features(
        self, orders: List[ShopifyOrder], events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute time series features"""
        # Implementation extracted from original service
        return {
            "total_orders": len(orders),
            "total_events": len(events),
        }
