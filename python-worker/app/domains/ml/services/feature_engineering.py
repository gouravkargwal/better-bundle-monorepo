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
    ShopifyCustomerEvent,
)

from .feature_pipeline import FeaturePipeline, IFeaturePipeline
from ..repositories.feature_repository import FeatureRepository, IFeatureRepository
from ..generators import (
    ProductFeatureGenerator,
    CustomerFeatureGenerator,
    OrderFeatureGenerator,
    CollectionFeatureGenerator,
    ShopFeatureGenerator,
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
        self.customer_generator = CustomerFeatureGenerator()
        self.order_generator = OrderFeatureGenerator()
        self.collection_generator = CollectionFeatureGenerator()
        self.shop_generator = ShopFeatureGenerator()

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

    async def compute_customer_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a customer using the customer generator"""
        try:
            context = {
                "shop": shop,
                "orders": orders or [],
                "events": events or [],
            }
            return await self.customer_generator.generate_features(customer, context)
        except Exception as e:
            logger.error(
                f"Failed to compute customer features for {customer.id}: {str(e)}"
            )
            return {}

    async def compute_order_features(
        self,
        order: ShopifyOrder,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for an order using the order generator"""
        try:
            context = {
                "shop": shop,
                "products": products or [],
            }
            return await self.order_generator.generate_features(order, context)
        except Exception as e:
            logger.error(f"Failed to compute order features for {order.id}: {str(e)}")
            return {}

    async def compute_collection_features(
        self,
        collection: ShopifyCollection,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a collection using the collection generator"""
        try:
            context = {
                "shop": shop,
                "products": products or [],
            }
            return await self.collection_generator.generate_features(
                collection, context
            )
        except Exception as e:
            logger.error(
                f"Failed to compute collection features for {collection.id}: {str(e)}"
            )
            return {}

    async def compute_shop_features(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a shop using the shop generator"""
        try:
            context = {
                "products": products or [],
                "orders": orders or [],
                "customers": customers or [],
                "collections": collections or [],
                "events": events or [],
            }
            return await self.shop_generator.generate_features(shop, context)
        except Exception as e:
            logger.error(f"Failed to compute shop features for {shop.id}: {str(e)}")
            return {}

    async def compute_cross_entity_features(
        self,
        shop: ShopifyShop,
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        customers: List[ShopifyCustomer],
        collections: List[ShopifyCollection],
        events: List[ShopifyCustomerEvent],
    ) -> Dict[str, Any]:
        """Compute cross-entity ML features"""
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
        events: List[ShopifyCustomerEvent],
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
        self, orders: List[ShopifyOrder], events: List[ShopifyCustomerEvent]
    ) -> Dict[str, Any]:
        """Compute time series features"""
        # Implementation extracted from original service
        return {
            "total_orders": len(orders),
            "total_events": len(events),
        }
