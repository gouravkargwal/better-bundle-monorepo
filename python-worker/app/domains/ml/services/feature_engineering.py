"""
Feature engineering service implementation for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
import math

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.core.database.simple_db_client import get_database

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

logger = get_logger(__name__)


class FeatureEngineeringService(IFeatureEngineeringService):
    """Feature engineering service for transforming Shopify data into ML features"""

    def __init__(self):
        # Feature computation settings
        self.max_features_per_entity = 100
        self.feature_quality_threshold = 0.7

        # Feature schemas for validation
        self.feature_schemas = self._initialize_feature_schemas()

        # Feature importance weights
        self.feature_importance_weights = self._initialize_feature_importance()

        # Database client
        self._db_client = None

    async def compute_product_features(
        self,
        product: ShopifyProduct,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a product"""
        try:
            logger.debug(f"Computing features for product: {product.id}")

            features = {}

            # Basic product features
            features.update(self._compute_basic_product_features(product))

            # Variant features
            features.update(self._compute_variant_features(product))

            # Image features
            features.update(self._compute_image_features(product))

            # Tag and category features
            features.update(self._compute_tag_features(product))

            # Collection features
            if collections:
                features.update(self._compute_collection_features(product, collections))

            # Historical performance features (if orders available)
            if orders:
                features.update(self._compute_performance_features(product, orders))

            # Shop context features
            features.update(self._compute_shop_context_features(product, shop))

            # Time-based features
            features.update(self._compute_time_features(product))

            # Quality features
            features.update(self._compute_quality_features(product))

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(f"Computed {len(features)} features for product: {product.id}")
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute product features",
                product_id=product.id,
                error=str(e),
            )
            raise

    async def compute_customer_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a customer"""
        try:
            logger.debug(f"Computing features for customer: {customer.id}")

            features = {}

            # Basic customer features
            features.update(self._compute_basic_customer_features(customer))

            # Order history features
            if orders:
                customer_orders = [o for o in orders if o.customer_id == customer.id]
                features.update(
                    self._compute_order_history_features(customer, customer_orders)
                )

            # Behavioral features
            if events:
                customer_events = [e for e in events if e.customer_id == customer.id]
                features.update(
                    self._compute_behavioral_features(customer, customer_events)
                )

            # Address features
            features.update(self._compute_address_features(customer))

            # Time-based features
            features.update(self._compute_customer_time_features(customer))

            # Engagement features
            features.update(self._compute_engagement_features(customer))

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(
                f"Computed {len(features)} features for customer: {customer.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute customer features",
                customer_id=customer.id,
                error=str(e),
            )
            raise

    async def compute_order_features(
        self,
        order: ShopifyOrder,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for an order"""
        try:
            logger.debug(f"Computing features for order: {order.id}")

            features = {}

            # Basic order features
            features.update(self._compute_basic_order_features(order))

            # Line item features
            features.update(self._compute_line_item_features(order))

            # Customer features
            features.update(self._compute_order_customer_features(order))

            # Product context features
            if products:
                order_products = [
                    p
                    for p in products
                    if p.id in [item.product_id for item in order.line_items]
                ]
                features.update(
                    self._compute_order_product_features(order, order_products)
                )

            # Time-based features
            features.update(self._compute_order_time_features(order))

            # Financial features
            features.update(self._compute_financial_features(order))

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(f"Computed {len(features)} features for order: {order.id}")
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute order features", order_id=order.id, error=str(e)
            )
            raise

    async def compute_collection_features(
        self,
        collection: ShopifyCollection,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a collection"""
        try:
            logger.debug(f"Computing features for collection: {collection.id}")

            features = {}

            # Basic collection features
            features.update(self._compute_basic_collection_features(collection))

            # Product features
            if products:
                collection_products = [
                    p for p in products if p.id in collection.product_ids
                ]
                features.update(
                    self._compute_collection_product_features(
                        collection, collection_products
                    )
                )

            # SEO features
            features.update(self._compute_seo_features(collection))

            # Time-based features
            features.update(self._compute_collection_time_features(collection))

            # Performance features
            features.update(self._compute_collection_performance_features(collection))

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(
                f"Computed {len(features)} features for collection: {collection.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute collection features",
                collection_id=collection.id,
                error=str(e),
            )
            raise

    async def compute_shop_features(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute ML features for a shop"""
        try:
            logger.debug(f"Computing features for shop: {shop.id}")

            features = {}

            # Basic shop features
            features.update(self._compute_basic_shop_features(shop))

            # Aggregate product features
            if products:
                features.update(self._compute_aggregate_product_features(products))

            # Aggregate order features
            if orders:
                features.update(self._compute_aggregate_order_features(orders))

            # Aggregate customer features
            if customers:
                features.update(self._compute_aggregate_customer_features(customers))

            # Aggregate collection features
            if collections:
                features.update(
                    self._compute_aggregate_collection_features(collections)
                )

            # Aggregate event features
            if events:
                features.update(self._compute_aggregate_event_features(events))

            # Cross-entity features
            if all([products, orders, customers, collections]):
                features.update(
                    self._compute_cross_entity_features(
                        products, orders, customers, collections
                    )
                )

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(f"Computed {len(features)} features for shop: {shop.id}")
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute shop features", shop_id=shop.id, error=str(e)
            )
            raise

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
            logger.debug(f"Computing cross-entity features for shop: {shop.id}")

            features = {}

            # Product-customer interaction features
            features.update(
                self._compute_product_customer_interactions(products, customers, orders)
            )

            # Collection-performance features
            features.update(
                self._compute_collection_performance_features_batch(
                    collections, products, orders
                )
            )

            # Customer-segment features
            features.update(
                self._compute_customer_segment_features(customers, orders, events)
            )

            # Product-category features
            features.update(
                self._compute_product_category_features(products, collections)
            )

            # Time-series features
            features.update(self._compute_time_series_features(orders, events))

            # Validate and clean features
            features = self._clean_features(features)

            logger.debug(
                f"Computed {len(features)} cross-entity features for shop: {shop.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute cross-entity features",
                shop_id=shop.id,
                error=str(e),
            )
            raise

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
            # Count features and identify missing ones
            feature_count = len(features)
            missing_features = self._identify_missing_features(features, feature_type)

            # Create MLFeatures instance
            ml_features = MLFeatures(
                id=f"{shop_id}_{feature_type}_{entity_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                feature_type=feature_type,
                entity_id=entity_id,
                computed_at=now_utc(),
                feature_version="1.0",
                data_sources=data_sources,
                feature_count=feature_count,
                missing_features=missing_features,
                feature_quality_score=self._calculate_feature_quality(
                    features, feature_type
                ),
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Set entity-specific features
            if feature_type == "product":
                ml_features.product_features = features
            elif feature_type == "customer":
                ml_features.customer_features = features
            elif feature_type == "order":
                ml_features.order_features = features
            elif feature_type == "collection":
                ml_features.collection_features = features
            elif feature_type == "shop":
                ml_features.advanced_features = features

            logger.debug(f"Created MLFeatures for {feature_type}: {entity_id}")
            return ml_features

        except Exception as e:
            logger.error(
                f"Failed to create MLFeatures",
                shop_id=shop_id,
                feature_type=feature_type,
                entity_id=entity_id,
                error=str(e),
            )
            raise

    async def validate_features(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, Any]:
        """Validate computed features"""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "feature_count": len(features),
                "missing_features": [],
                "quality_score": 0.0,
            }

            # Check feature count
            if len(features) == 0:
                validation_result["is_valid"] = False
                validation_result["errors"].append("No features computed")

            # Check for missing features
            schema = self.feature_schemas.get(feature_type, {})
            missing_features = []
            for expected_feature in schema.get("required_features", []):
                if expected_feature not in features:
                    missing_features.append(expected_feature)

            if missing_features:
                validation_result["warnings"].append(
                    f"Missing {len(missing_features)} expected features"
                )
                validation_result["missing_features"] = missing_features

            # Check feature quality
            quality_score = self._calculate_feature_quality(features, feature_type)
            validation_result["quality_score"] = quality_score

            if quality_score < self.feature_quality_threshold:
                validation_result["warnings"].append(
                    f"Low feature quality score: {quality_score:.2f}"
                )

            # Check for invalid values
            invalid_features = self._check_invalid_values(features)
            if invalid_features:
                validation_result["warnings"].append(
                    f"Found {len(invalid_features)} features with invalid values"
                )

            return validation_result

        except Exception as e:
            logger.error(
                f"Failed to validate features", feature_type=feature_type, error=str(e)
            )
            raise

    async def get_feature_schema(self, feature_type: str) -> Dict[str, Any]:
        """Get feature schema for a type"""
        return self.feature_schemas.get(feature_type, {})

    async def get_feature_importance(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, float]:
        """Get feature importance scores"""
        try:
            importance_weights = self.feature_importance_weights.get(feature_type, {})
            importance_scores = {}

            for feature_name, feature_value in features.items():
                base_weight = importance_weights.get(feature_name, 0.5)

                # Adjust weight based on feature value quality
                if (
                    isinstance(feature_value, (int, float))
                    and feature_value is not None
                ):
                    # Higher values get higher importance for numeric features
                    value_factor = (
                        min(1.0, abs(feature_value) / 1000.0)
                        if feature_value != 0
                        else 0.5
                    )
                    importance_scores[feature_name] = base_weight * (
                        0.5 + 0.5 * value_factor
                    )
                else:
                    # Categorical features get base weight
                    importance_scores[feature_name] = base_weight

            return importance_scores

        except Exception as e:
            logger.error(
                f"Failed to get feature importance",
                feature_type=feature_type,
                error=str(e),
            )
            return {}

    async def normalize_features(
        self,
        features: Dict[str, Any],
        feature_type: str,
        normalization_method: str = "standard",
    ) -> Dict[str, Any]:
        """Normalize features for ML training"""
        try:
            normalized_features = {}

            for feature_name, feature_value in features.items():
                if (
                    isinstance(feature_value, (int, float))
                    and feature_value is not None
                ):
                    if normalization_method == "standard":
                        # Standard scaling (z-score)
                        normalized_features[feature_name] = (feature_value - 0) / max(
                            1, abs(feature_value)
                        )
                    elif normalization_method == "minmax":
                        # Min-max scaling to [0, 1]
                        normalized_features[feature_name] = max(
                            0, min(1, feature_value / 1000)
                        )
                    elif normalization_method == "robust":
                        # Robust scaling
                        normalized_features[feature_name] = feature_value / max(
                            1, abs(feature_value)
                        )
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
                if isinstance(feature_value, str) and feature_value is not None:
                    if encoding_method == "one_hot":
                        # One-hot encoding
                        encoded_features[f"{feature_name}_{feature_value}"] = 1
                    elif encoding_method == "label":
                        # Label encoding (hash-based)
                        encoded_features[feature_name] = hash(feature_value) % 1000
                    else:
                        encoded_features[feature_name] = feature_value
                else:
                    encoded_features[feature_name] = feature_value

            return encoded_features

        except Exception as e:
            logger.error(
                f"Failed to encode categorical features",
                feature_type=feature_type,
                error=str(e),
            )
            return features

    async def compute_feature_statistics(
        self, features_list: List[Dict[str, Any]], feature_type: str
    ) -> Dict[str, Any]:
        """Compute statistics across multiple feature sets"""
        try:
            if not features_list:
                return {}

            # Get all feature names
            all_feature_names = set()
            for features in features_list:
                all_feature_names.update(features.keys())

            statistics = {}

            for feature_name in all_feature_names:
                values = []
                for features in features_list:
                    if feature_name in features:
                        value = features[feature_name]
                        if isinstance(value, (int, float)) and value is not None:
                            values.append(value)

                if values:
                    statistics[feature_name] = {
                        "count": len(values),
                        "mean": statistics.mean(values) if len(values) > 0 else 0,
                        "std": statistics.stdev(values) if len(values) > 1 else 0,
                        "min": min(values),
                        "max": max(values),
                        "median": statistics.median(values) if len(values) > 0 else 0,
                    }

            return statistics

        except Exception as e:
            logger.error(
                f"Failed to compute feature statistics",
                feature_type=feature_type,
                error=str(e),
            )
            return {}

    # Private helper methods for feature computation

    def _compute_basic_product_features(
        self, product: ShopifyProduct
    ) -> Dict[str, Any]:
        """Compute basic product features"""
        return {
            "product_id": product.id,
            "title_length": len(product.title or ""),
            "description_length": len(product.body_html or ""),
            "vendor_encoded": hash(product.vendor) % 1000,
            "product_type_encoded": hash(product.product_type) % 1000,
            "status_encoded": 1 if product.status == "active" else 0,
            "is_published": 1 if product.is_published else 0,
            "variant_count": product.variant_count,
            "has_multiple_variants": 1 if product.has_multiple_variants else 0,
            "tag_count": product.tag_count,
            "collection_count": product.collection_count,
            "has_images": 1 if product.has_images else 0,
            "image_count": product.image_count,
        }

    def _compute_variant_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute variant-related features"""
        if not product.variants:
            return {}

        prices = [v.price for v in product.variants if v.price > 0]
        weights = [v.weight for v in product.variants if v.weight and v.weight > 0]
        inventory = [v.inventory_quantity for v in product.variants]

        features = {
            "avg_price": statistics.mean(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "price_range": max(prices) - min(prices) if len(prices) > 1 else 0,
            "avg_weight": statistics.mean(weights) if weights else 0,
            "total_inventory": sum(inventory),
            "avg_inventory": statistics.mean(inventory) if inventory else 0,
            "has_discounts": 1 if any(v.has_discount for v in product.variants) else 0,
            "discount_variants_count": sum(
                1 for v in product.variants if v.has_discount
            ),
        }

        return features

    def _compute_image_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute image-related features"""
        return {
            "image_count": product.image_count,
            "has_main_image": 1 if product.main_image_url else 0,
            "image_density": product.image_count / max(1, product.variant_count),
        }

    def _compute_tag_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute tag-related features"""
        return {
            "tag_count": product.tag_count,
            "tag_diversity": len(set(product.tags)),
            "has_tags": 1 if product.tags else 0,
        }

    def _compute_collection_features(
        self, product: ShopifyProduct, collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute collection-related features"""
        product_collections = [c for c in collections if product.id in c.product_ids]

        return {
            "collection_count": len(product_collections),
            "automated_collections": sum(
                1 for c in product_collections if c.is_automated
            ),
            "manual_collections": sum(1 for c in product_collections if c.is_manual),
            "avg_collection_size": (
                statistics.mean([c.products_count for c in product_collections])
                if product_collections
                else 0
            ),
        }

    def _compute_performance_features(
        self, product: ShopifyProduct, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute historical performance features"""
        product_orders = []
        for order in orders:
            for item in order.line_items:
                if item.product_id == product.id:
                    product_orders.append((order, item))

        if not product_orders:
            return {"total_orders": 0, "total_quantity": 0, "total_revenue": 0}

        total_quantity = sum(item.quantity for _, item in product_orders)
        total_revenue = sum(item.total_price for _, item in product_orders)

        return {
            "total_orders": len(product_orders),
            "total_quantity": total_quantity,
            "total_revenue": total_revenue,
            "avg_quantity_per_order": total_quantity / len(product_orders),
            "avg_revenue_per_order": total_revenue / len(product_orders),
        }

    def _compute_shop_context_features(
        self, product: ShopifyProduct, shop: ShopifyShop
    ) -> Dict[str, Any]:
        """Compute shop context features"""
        return {
            "shop_plan_encoded": hash(shop.plan_name or "") % 1000,
            "shop_currency_encoded": hash(shop.currency or "") % 1000,
            "shop_country_encoded": hash(shop.country or "") % 1000,
            "shop_has_marketing": 1 if shop.has_marketing else 0,
            "shop_has_discounts": 1 if shop.has_discounts else 0,
        }

    def _compute_time_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute time-based features"""
        now = now_utc()

        return {
            "days_since_creation": (
                (now - product.created_at).days if product.created_at else 0
            ),
            "days_since_update": (
                (now - product.updated_at).days if product.updated_at else 0
            ),
            "days_since_publication": (
                (now - product.published_at).days if product.published_at else 0
            ),
            "is_recent": (
                1 if product.created_at and (now - product.created_at).days < 30 else 0
            ),
            "is_updated_recently": (
                1 if product.updated_at and (now - product.updated_at).days < 7 else 0
            ),
        }

    def _compute_quality_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute quality-related features"""
        quality_score = 0.0

        # Title quality
        if product.title and len(product.title) > 10:
            quality_score += 0.2

        # Description quality
        if product.body_html and len(product.body_html) > 50:
            quality_score += 0.2

        # Image quality
        if product.has_images:
            quality_score += 0.2

        # Tag quality
        if product.tags and len(product.tags) > 2:
            quality_score += 0.2

        # Variant quality
        if product.variants and len(product.variants) > 0:
            quality_score += 0.2

        return {
            "quality_score": quality_score,
            "has_title": 1 if product.title else 0,
            "has_description": 1 if product.body_html else 0,
            "has_variants": 1 if product.variants else 0,
        }

    def _clean_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate features"""
        cleaned_features = {}

        for key, value in features.items():
            # Skip None values
            if value is None:
                continue

            # Convert to appropriate types
            if isinstance(value, (int, float)):
                if math.isnan(value) or math.isinf(value):
                    continue
                cleaned_features[key] = value
            elif isinstance(value, str):
                if value.strip():
                    cleaned_features[key] = value
            elif isinstance(value, bool):
                cleaned_features[key] = 1 if value else 0
            else:
                cleaned_features[key] = value

        return cleaned_features

    def _identify_missing_features(
        self, features: Dict[str, Any], feature_type: str
    ) -> List[str]:
        """Identify missing expected features"""
        schema = self.feature_schemas.get(feature_type, {})
        expected_features = schema.get("required_features", [])

        missing = []
        for expected in expected_features:
            if expected not in features:
                missing.append(expected)

        return missing

    def _calculate_feature_quality(
        self, features: Dict[str, Any], feature_type: str
    ) -> float:
        """Calculate overall feature quality score"""
        if not features:
            return 0.0

        # Count valid features
        valid_features = 0
        for value in features.values():
            if value is not None and not (
                isinstance(value, (int, float))
                and (math.isnan(value) or math.isinf(value))
            ):
                valid_features += 1

        return valid_features / len(features) if features else 0.0

    def _check_invalid_values(self, features: Dict[str, Any]) -> List[str]:
        """Check for features with invalid values"""
        invalid_features = []

        for feature_name, value in features.items():
            if isinstance(value, (int, float)) and (
                math.isnan(value) or math.isinf(value)
            ):
                invalid_features.append(feature_name)
            elif value is None:
                invalid_features.append(feature_name)

        return invalid_features

    def _initialize_feature_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Initialize feature schemas"""
        return {
            "product": {
                "required_features": [
                    "product_id",
                    "title_length",
                    "variant_count",
                    "tag_count",
                    "collection_count",
                    "has_images",
                    "image_count",
                ]
            },
            "customer": {
                "required_features": [
                    "customer_id",
                    "orders_count",
                    "total_spent",
                    "days_since_creation",
                ]
            },
            "order": {
                "required_features": [
                    "order_id",
                    "total_price",
                    "total_items",
                    "days_since_creation",
                ]
            },
            "collection": {
                "required_features": [
                    "collection_id",
                    "products_count",
                    "is_published",
                    "days_since_creation",
                ]
            },
            "shop": {
                "required_features": [
                    "shop_id",
                    "total_products",
                    "total_orders",
                    "total_customers",
                ]
            },
        }

    def _initialize_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Initialize feature importance weights"""
        return {
            "product": {
                "price": 0.9,
                "variant_count": 0.8,
                "image_count": 0.7,
                "tag_count": 0.6,
                "collection_count": 0.7,
            },
            "customer": {
                "orders_count": 0.9,
                "total_spent": 0.9,
                "days_since_creation": 0.6,
                "average_order_value": 0.8,
            },
            "order": {
                "total_price": 0.9,
                "total_items": 0.8,
                "days_since_creation": 0.5,
            },
        }

    # Additional helper methods for other entity types

    def _compute_basic_customer_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute basic customer features"""
        return {
            "customer_id": customer.id,
            "email_length": len(customer.email or ""),
            "first_name_length": len(customer.first_name or ""),
            "last_name_length": len(customer.last_name or ""),
            "orders_count": customer.orders_count,
            "total_spent": customer.total_spent,
            "has_phone": 1 if customer.phone else 0,
            "has_address": 1 if customer.default_address else 0,
            "is_verified": (
                1 if customer.email else 0
            ),  # Use email presence as verification
            "accepts_marketing": 1 if customer.accepts_marketing else 0,
            "tags_count": len(customer.tags) if customer.tags else 0,
        }

    def _compute_order_history_features(
        self, customer: ShopifyCustomer, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute order history features"""
        if not orders:
            return {"total_orders": 0, "total_spent": 0, "average_order_value": 0}

        total_spent = sum(order.total_price for order in orders)
        return {
            "total_orders": len(orders),
            "total_spent": total_spent,
            "average_order_value": total_spent / len(orders) if orders else 0,
            "largest_order": (
                max(order.total_price for order in orders) if orders else 0
            ),
            "smallest_order": (
                min(order.total_price for order in orders) if orders else 0
            ),
        }

    def _compute_behavioral_features(
        self, customer: ShopifyCustomer, events: List[ShopifyCustomerEvent]
    ) -> Dict[str, Any]:
        """Compute behavioral features"""
        if not events:
            return {"event_count": 0, "last_event_days": 0}

        event_types = [event.event_type for event in events]
        return {
            "event_count": len(events),
            "unique_event_types": len(set(event_types)),
            "most_common_event": (
                max(set(event_types), key=event_types.count) if event_types else ""
            ),
            "last_event_days": (
                (now_utc() - max(event.created_at for event in events)).days
                if events
                else 0
            ),
        }

    def _compute_address_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute address features"""
        if not customer.default_address:
            return {"has_address": 0, "country_encoded": 0}

        address = customer.default_address
        return {
            "has_address": 1,
            "country_encoded": hash(address.country or "") % 1000,
            "province_encoded": hash(address.province or "") % 1000,
            "city_encoded": hash(address.city or "") % 1000,
            "zip_length": len(address.zip or ""),
        }

    def _compute_customer_time_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute customer time features"""
        now = now_utc()
        return {
            "days_since_creation": (
                (now - customer.created_at).days if customer.created_at else 0
            ),
            "days_since_update": (
                (now - customer.updated_at).days if customer.updated_at else 0
            ),
            "is_recent_customer": (
                1
                if customer.created_at and (now - customer.created_at).days < 30
                else 0
            ),
        }

    def _compute_engagement_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute engagement features"""
        return {
            "engagement_score": min(
                1.0,
                (
                    customer.orders_count * 0.5
                    + (1 if customer.accepts_marketing else 0) * 0.3
                ),
            ),
            "loyalty_indicator": 1 if customer.orders_count > 5 else 0,
            "high_value_indicator": 1 if customer.total_spent > 1000 else 0,
        }

    def _compute_basic_order_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute basic order features"""
        return {
            "order_id": order.id,
            "total_price": order.total_price,
            "total_items": sum(item.quantity for item in order.line_items),
            "line_items_count": len(order.line_items),
            "currency_encoded": hash(order.currency or "") % 1000,
            "financial_status_encoded": hash(order.financial_status or "") % 1000,
            "fulfillment_status_encoded": hash(order.fulfillment_status or "") % 1000,
            "has_discounts": 1 if order.total_discounts > 0 else 0,
            "discount_amount": order.total_discounts,
        }

    def _compute_line_item_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute line item features"""
        return {
            "unique_products": len(set(item.product_id for item in order.line_items)),
            "average_item_price": (
                order.total_price / sum(item.quantity for item in order.line_items)
                if order.line_items
                else 0
            ),
            "largest_item_quantity": (
                max(item.quantity for item in order.line_items)
                if order.line_items
                else 0
            ),
        }

    def _compute_order_customer_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute order customer features"""
        return {
            "customer_id": order.customer_id,
            "customer_orders_count": (
                order.customer_orders_count
                if hasattr(order, "customer_orders_count")
                else 0
            ),
        }

    def _compute_order_product_features(
        self, order: ShopifyOrder, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute order product features"""
        order_product_ids = [item.product_id for item in order.line_items]
        order_products = [p for p in products if p.id in order_product_ids]

        if not order_products:
            return {}

        return {
            "product_categories": len(
                set(p.product_type for p in order_products if p.product_type)
            ),
            "average_product_price": (
                sum(p.price for p in order_products if p.price) / len(order_products)
                if order_products
                else 0
            ),
        }

    def _compute_order_time_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute order time features"""
        now = now_utc()
        return {
            "days_since_creation": (
                (now - order.created_at).days if order.created_at else 0
            ),
            "days_since_update": (
                (now - order.updated_at).days if order.updated_at else 0
            ),
            "is_recent_order": (
                1 if order.created_at and (now - order.created_at).days < 7 else 0
            ),
        }

    def _compute_financial_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute financial features"""
        return {
            "subtotal": order.subtotal_price,
            "tax_amount": order.total_tax,
            "shipping_amount": order.total_shipping_price_set,
            "net_amount": order.net_payment_refunded,
        }

    def _compute_basic_collection_features(
        self, collection: ShopifyCollection
    ) -> Dict[str, Any]:
        """Compute basic collection features"""
        return {
            "collection_id": collection.id,
            "title_length": len(collection.title or ""),
            "description_length": len(collection.description_html or ""),
            "products_count": collection.products_count,
            "is_published": 1 if collection.is_published else 0,
            "is_automated": 1 if collection.is_automated else 0,
            "is_manual": 1 if collection.is_manual else 0,
            "sort_order_encoded": hash(collection.sort_order or "") % 1000,
        }

    def _compute_collection_product_features(
        self, collection: ShopifyCollection, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute collection product features"""
        collection_products = [p for p in products if p.id in collection.product_ids]

        if not collection_products:
            return {}

        prices = [p.price for p in collection_products if p.price]
        return {
            "average_product_price": statistics.mean(prices) if prices else 0,
            "price_range": max(prices) - min(prices) if len(prices) > 1 else 0,
            "product_types_count": len(
                set(p.product_type for p in collection_products if p.product_type)
            ),
        }

    def _compute_seo_features(self, collection: ShopifyCollection) -> Dict[str, Any]:
        """Compute SEO features"""
        return {
            "has_seo_title": 1 if collection.seo_title else 0,
            "has_seo_description": 1 if collection.seo_description else 0,
            "seo_title_length": len(collection.seo_title or ""),
            "seo_description_length": len(collection.seo_description or ""),
        }

    def _compute_collection_time_features(
        self, collection: ShopifyCollection
    ) -> Dict[str, Any]:
        """Compute collection time features"""
        now = now_utc()
        return {
            "days_since_creation": (
                (now - collection.created_at).days if collection.created_at else 0
            ),
            "days_since_update": (
                (now - collection.updated_at).days if collection.updated_at else 0
            ),
            "is_recent": (
                1
                if collection.created_at and (now - collection.created_at).days < 30
                else 0
            ),
        }

    def _compute_collection_performance_features(
        self, collection: ShopifyCollection
    ) -> Dict[str, Any]:
        """Compute collection performance features"""
        return {
            "product_density": collection.products_count
            / max(1, collection.products_count),
            "has_products": 1 if collection.products_count > 0 else 0,
        }

    def _compute_basic_shop_features(self, shop: ShopifyShop) -> Dict[str, Any]:
        """Compute basic shop features"""
        return {
            "shop_id": shop.id,
            "name_length": len(shop.name or ""),
            "domain_length": len(shop.domain or ""),
            "plan_encoded": hash(shop.plan_name or "") % 1000,
            "currency_encoded": hash(shop.currency or "") % 1000,
            "country_encoded": hash(shop.country or "") % 1000,
            "timezone_encoded": hash(shop.iana_timezone or "") % 1000,
            "has_marketing": 1 if shop.has_marketing else 0,
            "has_discounts": 1 if shop.has_discounts else 0,
            "has_gift_cards": 1 if shop.has_gift_cards else 0,
        }

    def _compute_aggregate_product_features(
        self, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute aggregate product features"""
        if not products:
            return {}

        prices = [p.price for p in products if p.price]
        return {
            "total_products": len(products),
            "active_products": sum(1 for p in products if p.status == "active"),
            "published_products": sum(1 for p in products if p.is_published),
            "average_price": statistics.mean(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "total_variants": sum(p.variant_count for p in products),
        }

    def _compute_aggregate_order_features(
        self, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute aggregate order features"""
        if not orders:
            return {}

        prices = [o.total_price for o in orders]
        return {
            "total_orders": len(orders),
            "total_revenue": sum(prices),
            "average_order_value": statistics.mean(prices) if prices else 0,
            "largest_order": max(prices) if prices else 0,
            "orders_with_discounts": sum(1 for o in orders if o.total_discounts > 0),
        }

    def _compute_aggregate_customer_features(
        self, customers: List[ShopifyCustomer]
    ) -> Dict[str, Any]:
        """Compute aggregate customer features"""
        if not customers:
            return {}

        spent_values = [c.total_spent for c in customers]
        return {
            "total_customers": len(customers),
            "total_customer_spend": sum(spent_values),
            "average_customer_spend": (
                statistics.mean(spent_values) if spent_values else 0
            ),
            "high_value_customers": sum(1 for c in customers if c.total_spent > 1000),
            "customers_with_orders": sum(1 for c in customers if c.orders_count > 0),
        }

    def _compute_aggregate_collection_features(
        self, collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute aggregate collection features"""
        if not collections:
            return {}

        return {
            "total_collections": len(collections),
            "published_collections": sum(1 for c in collections if c.is_published),
            "automated_collections": sum(1 for c in collections if c.is_automated),
            "manual_collections": sum(1 for c in collections if c.is_manual),
            "total_collection_products": sum(c.products_count for c in collections),
        }

    def _compute_aggregate_event_features(
        self, events: List[ShopifyCustomerEvent]
    ) -> Dict[str, Any]:
        """Compute aggregate event features"""
        if not events:
            return {}

        event_types = [e.event_type for e in events]
        return {
            "total_events": len(events),
            "unique_event_types": len(set(event_types)),
            "most_common_event": (
                max(set(event_types), key=event_types.count) if event_types else ""
            ),
            "recent_events": sum(
                1 for e in events if (now_utc() - e.created_at).days < 7
            ),
        }

    def _compute_cross_entity_features(
        self,
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        customers: List[ShopifyCustomer],
        collections: List[ShopifyCollection],
    ) -> Dict[str, Any]:
        """Compute cross-entity features"""
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

    def _compute_product_customer_interactions(
        self,
        products: List[ShopifyProduct],
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
    ) -> Dict[str, Any]:
        """Compute product-customer interaction features"""
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
        return {
            "collections_with_products": sum(
                1 for c in collections if c.products_count > 0
            ),
            "average_collection_size": (
                statistics.mean([c.products_count for c in collections])
                if collections
                else 0
            ),
            "largest_collection": (
                max(c.products_count for c in collections) if collections else 0
            ),
        }

    def _compute_customer_segment_features(
        self,
        customers: List[ShopifyCustomer],
        orders: List[ShopifyOrder],
        events: List[ShopifyCustomerEvent],
    ) -> Dict[str, Any]:
        """Compute customer segment features"""
        return {
            "customer_segments": {
                "high_value": sum(1 for c in customers if c.total_spent > 1000),
                "medium_value": sum(
                    1 for c in customers if 100 <= c.total_spent <= 1000
                ),
                "low_value": sum(1 for c in customers if c.total_spent < 100),
            },
            "active_customers": sum(1 for c in customers if c.orders_count > 0),
        }

    def _compute_product_category_features(
        self, products: List[ShopifyProduct], collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute product category features"""
        return {
            "unique_product_types": len(
                set(p.product_type for p in products if p.product_type)
            ),
            "products_in_collections": sum(
                1 for p in products if p.collection_count > 0
            ),
            "average_collections_per_product": (
                statistics.mean([p.collection_count for p in products])
                if products
                else 0
            ),
        }

    def _compute_time_series_features(
        self, orders: List[ShopifyOrder], events: List[ShopifyCustomerEvent]
    ) -> Dict[str, Any]:
        """Compute time series features"""
        if not orders:
            return {}

        order_dates = [o.created_at for o in orders if o.created_at]
        if not order_dates:
            return {}

        return {
            "order_date_range": (max(order_dates) - min(order_dates)).days,
            "orders_per_day": len(orders)
            / max(1, (max(order_dates) - min(order_dates)).days),
            "recent_orders": sum(
                1 for o in orders if (now_utc() - o.created_at).days < 30
            ),
        }

    # Additional helper methods for missing functionality

    def _compute_order_features(
        self,
        order: ShopifyOrder,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute order features"""
        features = {}
        features.update(self._compute_basic_order_features(order))
        features.update(self._compute_line_item_features(order))
        features.update(self._compute_order_customer_features(order))

        if products:
            features.update(self._compute_order_product_features(order, products))

        features.update(self._compute_order_time_features(order))
        features.update(self._compute_financial_features(order))

        return features

    def _compute_collection_features(
        self,
        collection: ShopifyCollection,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """Compute collection features"""
        features = {}
        features.update(self._compute_basic_collection_features(collection))

        if products:
            features.update(
                self._compute_collection_product_features(collection, products)
            )

        features.update(self._compute_seo_features(collection))
        features.update(self._compute_collection_time_features(collection))
        features.update(self._compute_collection_performance_features(collection))

        return features

    def _compute_customer_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute customer features"""
        features = {}
        features.update(self._compute_basic_customer_features(customer))

        if orders:
            customer_orders = [o for o in orders if o.customer_id == customer.id]
            features.update(
                self._compute_order_history_features(customer, customer_orders)
            )

        if events:
            customer_events = [e for e in events if e.customer_id == customer.id]
            features.update(
                self._compute_behavioral_features(customer, customer_events)
            )

        features.update(self._compute_address_features(customer))
        features.update(self._compute_customer_time_features(customer))
        features.update(self._compute_engagement_features(customer))

        return features

    def _compute_shop_features(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """Compute shop features"""
        features = {}
        features.update(self._compute_basic_shop_features(shop))

        if products:
            features.update(self._compute_aggregate_product_features(products))

        if orders:
            features.update(self._compute_aggregate_order_features(orders))

        if customers:
            features.update(self._compute_aggregate_customer_features(customers))

        if collections:
            features.update(self._compute_aggregate_collection_features(collections))

        if events:
            features.update(self._compute_aggregate_event_features(events))

        if all([products, orders, customers, collections]):
            features.update(
                self._compute_cross_entity_features(
                    products, orders, customers, collections
                )
            )

        return features

    def _compute_cross_entity_features(
        self,
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        customers: List[ShopifyCustomer],
        collections: List[ShopifyCollection],
    ) -> Dict[str, Any]:
        """Compute cross-entity features"""
        features = {}
        features.update(
            self._compute_product_customer_interactions(products, customers, orders)
        )
        features.update(
            self._compute_collection_performance_features_batch(
                collections, products, orders
            )
        )
        features.update(self._compute_customer_segment_features(customers, orders, []))
        features.update(self._compute_product_category_features(products, collections))
        features.update(self._compute_time_series_features(orders, []))

        return features

    # Main table data reading and feature pipeline methods

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def run_feature_pipeline_for_shop(
        self, shop_id: str, batch_size: int = 100
    ) -> Dict[str, Any]:
        """Run complete feature engineering pipeline for a shop using batch processing"""
        try:
            logger.info(f"Starting feature pipeline for shop: {shop_id}")

            # Read shop info only
            shop_data = await self._read_shop_data_from_main_tables(shop_id)
            if not shop_data:
                logger.warning(f"No shop found: {shop_id}")
                return {"success": False, "message": "No shop found"}

            shop = shop_data["shop"]
            results = {}

            # Process products in batches
            product_count = await self._get_entity_count(shop_id, "products")
            if product_count > 0:
                logger.info(
                    f"Processing {product_count} products in batches of {batch_size}"
                )
                results["product_features"] = await self._process_products_batch(
                    shop_id, shop, batch_size, product_count
                )

            # Process customers in batches
            customer_count = await self._get_entity_count(shop_id, "customers")
            if customer_count > 0:
                logger.info(
                    f"Processing {customer_count} customers in batches of {batch_size}"
                )
                results["customer_features"] = await self._process_customers_batch(
                    shop_id, shop, batch_size, customer_count
                )

            # Process collections in batches
            collection_count = await self._get_entity_count(shop_id, "collections")
            if collection_count > 0:
                logger.info(
                    f"Processing {collection_count} collections in batches of {batch_size}"
                )
                results["collection_features"] = await self._process_collections_batch(
                    shop_id, shop, batch_size, collection_count
                )

            # Process interactions in batches
            order_count = await self._get_entity_count(shop_id, "orders")
            if order_count > 0:
                logger.info(
                    f"Processing {order_count} orders for interactions in batches of {batch_size}"
                )
                results["interaction_features"] = (
                    await self._process_interactions_batch(
                        shop_id, batch_size, order_count
                    )
                )

            logger.info(f"Feature pipeline completed for shop: {shop_id}")
            return {"success": True, "results": results}

        except Exception as e:
            logger.error(f"Feature pipeline failed for shop {shop_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _read_shop_data_from_main_tables(self, shop_id: str) -> Dict[str, Any]:
        """Read shop info only - other data will be loaded in batches"""
        try:
            db = await self._get_database()

            # Read shop info only
            shop_result = await db.query_raw(
                'SELECT * FROM "Shop" WHERE id = $1', shop_id
            )
            if not shop_result:
                return None
            shop_data = shop_result[0]

            return {
                "shop": self._convert_shop_data(shop_data),
                "shop_id": shop_id,
            }

        except Exception as e:
            logger.error(f"Failed to read shop data: {str(e)}")
            return None

    async def _get_entity_count(self, shop_id: str, entity_type: str) -> int:
        """Get count of entities for a shop"""
        try:
            db = await self._get_database()

            table_map = {
                "products": "ProductData",
                "customers": "CustomerData",
                "orders": "OrderData",
                "collections": "CollectionData",
                "events": "CustomerEventData",
            }

            table_name = table_map.get(entity_type)
            if not table_name:
                return 0

            result = await db.query_raw(
                f'SELECT COUNT(*) as count FROM "{table_name}" WHERE "shopId" = $1',
                shop_id,
            )
            return result[0]["count"] if result else 0

        except Exception as e:
            logger.error(f"Failed to get {entity_type} count: {str(e)}")
            return 0

    async def _read_entities_batch(
        self, shop_id: str, entity_type: str, offset: int, limit: int
    ) -> List[Dict]:
        """Read a batch of entities from main tables"""
        try:
            db = await self._get_database()

            table_map = {
                "products": ("ProductData", self._convert_product_data),
                "customers": ("CustomerData", self._convert_customer_data),
                "orders": ("OrderData", self._convert_order_data),
                "collections": ("CollectionData", self._convert_collection_data),
                "events": ("CustomerEventData", self._convert_event_data),
            }

            table_name, converter = table_map.get(entity_type, (None, None))
            if not table_name or not converter:
                return []

            result = await db.query_raw(
                f'SELECT * FROM "{table_name}" WHERE "shopId" = $1 ORDER BY id LIMIT $2 OFFSET $3',
                shop_id,
                limit,
                offset,
            )

            return [converter(row) for row in result]

        except Exception as e:
            logger.error(f"Failed to read {entity_type} batch: {str(e)}")
            return []

    # Batch processing methods

    async def _process_products_batch(
        self, shop_id: str, shop: Dict, batch_size: int, total_count: int
    ) -> Dict[str, Any]:
        """Process products in batches to avoid memory issues"""
        total_saved = 0
        total_processed = 0

        for offset in range(0, total_count, batch_size):
            # Load batch of products
            products_batch = await self._read_entities_batch(
                shop_id, "products", offset, batch_size
            )
            if not products_batch:
                break

            # Process and save batch
            batch_result = await self._compute_and_save_product_features_batch(
                shop_id, products_batch, shop
            )
            total_saved += batch_result.get("saved_count", 0)
            total_processed += len(products_batch)

            logger.debug(
                f"Processed product batch {offset//batch_size + 1}: {len(products_batch)} products"
            )

        return {"saved_count": total_saved, "total_processed": total_processed}

    async def _process_customers_batch(
        self, shop_id: str, shop: Dict, batch_size: int, total_count: int
    ) -> Dict[str, Any]:
        """Process customers in batches"""
        total_saved = 0
        total_processed = 0

        for offset in range(0, total_count, batch_size):
            # Load batch of customers
            customers_batch = await self._read_entities_batch(
                shop_id, "customers", offset, batch_size
            )
            if not customers_batch:
                break

            # Process and save batch
            batch_result = await self._compute_and_save_customer_features_batch(
                shop_id, customers_batch, shop
            )
            total_saved += batch_result.get("saved_count", 0)
            total_processed += len(customers_batch)

            logger.debug(
                f"Processed customer batch {offset//batch_size + 1}: {len(customers_batch)} customers"
            )

        return {"saved_count": total_saved, "total_processed": total_processed}

    async def _process_collections_batch(
        self, shop_id: str, shop: Dict, batch_size: int, total_count: int
    ) -> Dict[str, Any]:
        """Process collections in batches"""
        total_saved = 0
        total_processed = 0

        for offset in range(0, total_count, batch_size):
            # Load batch of collections
            collections_batch = await self._read_entities_batch(
                shop_id, "collections", offset, batch_size
            )
            if not collections_batch:
                break

            # Process and save batch
            batch_result = await self._compute_and_save_collection_features_batch(
                shop_id, collections_batch, shop
            )
            total_saved += batch_result.get("saved_count", 0)
            total_processed += len(collections_batch)

            logger.debug(
                f"Processed collection batch {offset//batch_size + 1}: {len(collections_batch)} collections"
            )

        return {"saved_count": total_saved, "total_processed": total_processed}

    async def _process_interactions_batch(
        self, shop_id: str, batch_size: int, total_count: int
    ) -> Dict[str, Any]:
        """Process interactions in batches"""
        total_saved = 0
        total_processed = 0

        for offset in range(0, total_count, batch_size):
            # Load batch of orders
            orders_batch = await self._read_entities_batch(
                shop_id, "orders", offset, batch_size
            )
            if not orders_batch:
                break

            # Process and save batch
            batch_result = await self._compute_and_save_interaction_features_batch(
                shop_id, orders_batch
            )
            total_saved += batch_result.get("saved_count", 0)
            total_processed += len(orders_batch)

            logger.debug(
                f"Processed interaction batch {offset//batch_size + 1}: {len(orders_batch)} orders"
            )

        return {"saved_count": total_saved, "total_processed": total_processed}

    # Batch feature computation and saving methods (fixes N+1 problem)

    async def _compute_and_save_product_features_batch(
        self, shop_id: str, products: List[ShopifyProduct], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save product features in batch to avoid N+1 writes"""
        try:
            db = await self._get_database()

            # Prepare batch data
            batch_data = []
            for product in products:
                features = await self.compute_product_features(product, shop)

                batch_data.append(
                    (
                        shop_id,
                        product.id,
                        features.get("total_orders", 0),
                        self._get_price_tier(features.get("avg_price", 0)),
                        product.product_type,
                        features.get("variant_count", 0) / 10.0,
                        features.get("image_count", 0) / 10.0,
                        features.get("tag_diversity", 0) / 10.0,
                        1 if product.product_type else 0,
                        1 if product.vendor else 0,
                        now_utc(),
                    )
                )

            if not batch_data:
                return {"saved_count": 0, "total_products": 0}

            # Use Prisma's upsert method for each product feature to handle auto-generated IDs
            saved_count = 0
            for product_data in batch_data:
                try:
                    # Try to find existing record first
                    existing = await db.productfeatures.find_first(
                        where={
                            "shopId": product_data[0],
                            "productId": product_data[1],
                        }
                    )

                    if existing:
                        # Update existing record
                        await db.productfeatures.update(
                            where={"id": existing.id},
                            data={
                                "popularity": product_data[2],
                                "priceTier": product_data[3],
                                "category": product_data[4],
                                "variantComplexity": product_data[5],
                                "imageRichness": product_data[6],
                                "tagDiversity": product_data[7],
                                "categoryEncoded": product_data[8],
                                "vendorScore": product_data[9],
                                "lastComputedAt": product_data[10],
                            },
                        )
                    else:
                        # Create new record
                        await db.productfeatures.create(
                            data={
                                "shopId": product_data[0],
                                "productId": product_data[1],
                                "popularity": product_data[2],
                                "priceTier": product_data[3],
                                "category": product_data[4],
                                "variantComplexity": product_data[5],
                                "imageRichness": product_data[6],
                                "tagDiversity": product_data[7],
                                "categoryEncoded": product_data[8],
                                "vendorScore": product_data[9],
                                "lastComputedAt": product_data[10],
                            }
                        )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert product feature: {str(e)}")
                    continue

            return {"saved_count": len(batch_data), "total_products": len(products)}

        except Exception as e:
            logger.error(f"Failed to save product features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_customer_features_batch(
        self, shop_id: str, customers: List[ShopifyCustomer], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save customer features in batch"""
        try:
            db = await self._get_database()

            # Prepare batch data for UserFeatures
            user_features_batch = []
            behavior_features_batch = []

            for customer in customers:

                # Get customer's orders and events (simplified for batch processing)
                features = await self.compute_customer_features(customer, shop, [], [])

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
                        features.get("recency_score", 0),
                        features.get("diversity_score", 0),
                        features.get("behavioral_score", 0),
                        now_utc(),
                    )
                )

            saved_count = 0

            # Use Prisma's upsert method for each user feature to handle auto-generated IDs
            if user_features_batch:
                for user_data in user_features_batch:
                    try:
                        # Try to find existing record first
                        existing = await db.userfeatures.find_first(
                            where={
                                "shopId": user_data[0],
                                "customerId": user_data[1],
                            }
                        )

                        if existing:
                            # Update existing record
                            await db.userfeatures.update(
                                where={"id": existing.id},
                                data={
                                    "totalPurchases": user_data[2],
                                    "totalSpent": user_data[3],
                                    "recencyDays": user_data[4],
                                    "avgPurchaseIntervalDays": user_data[5],
                                    "preferredCategory": user_data[6],
                                    "lastComputedAt": user_data[7],
                                },
                            )
                        else:
                            # Create new record
                            await db.userfeatures.create(
                                data={
                                    "shopId": user_data[0],
                                    "customerId": user_data[1],
                                    "totalPurchases": user_data[2],
                                    "totalSpent": user_data[3],
                                    "recencyDays": user_data[4],
                                    "avgPurchaseIntervalDays": user_data[5],
                                    "preferredCategory": user_data[6],
                                    "lastComputedAt": user_data[7],
                                }
                            )
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"Failed to upsert user feature: {str(e)}")
                        continue

            # Use Prisma's upsert method for each customer behavior feature to handle auto-generated IDs
            if behavior_features_batch:
                for behavior_data in behavior_features_batch:
                    try:
                        # Try to find existing record first
                        existing = await db.customerbehaviorfeatures.find_first(
                            where={
                                "shopId": behavior_data[0],
                                "customerId": behavior_data[1],
                            }
                        )

                        if existing:
                            # Update existing record
                            await db.customerbehaviorfeatures.update(
                                where={"id": existing.id},
                                data={
                                    "eventDiversity": behavior_data[2],
                                    "eventFrequency": behavior_data[3],
                                    "daysSinceFirstEvent": behavior_data[4],
                                    "daysSinceLastEvent": behavior_data[5],
                                    "purchaseFrequency": behavior_data[6],
                                    "engagementScore": behavior_data[7],
                                    "recencyScore": behavior_data[8],
                                    "diversityScore": behavior_data[9],
                                    "behavioralScore": behavior_data[10],
                                    "lastComputedAt": behavior_data[11],
                                },
                            )
                        else:
                            # Create new record
                            await db.customerbehaviorfeatures.create(
                                data={
                                    "shopId": behavior_data[0],
                                    "customerId": behavior_data[1],
                                    "eventDiversity": behavior_data[2],
                                    "eventFrequency": behavior_data[3],
                                    "daysSinceFirstEvent": behavior_data[4],
                                    "daysSinceLastEvent": behavior_data[5],
                                    "purchaseFrequency": behavior_data[6],
                                    "engagementScore": behavior_data[7],
                                    "recencyScore": behavior_data[8],
                                    "diversityScore": behavior_data[9],
                                    "behavioralScore": behavior_data[10],
                                    "lastComputedAt": behavior_data[11],
                                }
                            )
                        saved_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to upsert customer behavior feature: {str(e)}"
                        )
                        continue

            return {"saved_count": saved_count, "total_customers": len(customers)}

        except Exception as e:
            logger.error(f"Failed to save customer features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_collection_features_batch(
        self, shop_id: str, collections: List[ShopifyCollection], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save collection features in batch"""
        try:
            db = await self._get_database()

            # Prepare batch data
            batch_data = []
            for collection in collections:
                features = await self.compute_collection_features(collection, shop, [])

                batch_data.append(
                    (
                        shop_id,
                        collection.id,
                        features.get("products_count", 0),
                        features.get("is_automated", False),
                        features.get("performance_score", 0),
                        features.get("seo_score", 0),
                        features.get("image_score", 0),
                        now_utc(),
                    )
                )

            if not batch_data:
                return {"saved_count": 0, "total_collections": 0}

            # Use Prisma's upsert method for each collection feature to handle auto-generated IDs
            saved_count = 0
            for collection_data in batch_data:
                try:
                    # Try to find existing record first
                    existing = await db.collectionfeatures.find_first(
                        where={
                            "shopId": collection_data[0],
                            "collectionId": collection_data[1],
                        }
                    )

                    if existing:
                        # Update existing record
                        await db.collectionfeatures.update(
                            where={"id": existing.id},
                            data={
                                "productCount": collection_data[2],
                                "isAutomated": collection_data[3],
                                "performanceScore": collection_data[4],
                                "seoScore": collection_data[5],
                                "imageScore": collection_data[6],
                                "lastComputedAt": collection_data[7],
                            },
                        )
                    else:
                        # Create new record
                        await db.collectionfeatures.create(
                            data={
                                "shopId": collection_data[0],
                                "collectionId": collection_data[1],
                                "productCount": collection_data[2],
                                "isAutomated": collection_data[3],
                                "performanceScore": collection_data[4],
                                "seoScore": collection_data[5],
                                "imageScore": collection_data[6],
                                "lastComputedAt": collection_data[7],
                            }
                        )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert collection feature: {str(e)}")
                    continue

            return {
                "saved_count": saved_count,
                "total_collections": len(collections),
            }

        except Exception as e:
            logger.error(f"Failed to save collection features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_interaction_features_batch(
        self, shop_id: str, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute and save interaction features in batch"""
        try:
            db = await self._get_database()

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
                    order_date = order.created_at
                    if order_date and (
                        not interactions[key]["lastPurchaseDate"]
                        or order_date > interactions[key]["lastPurchaseDate"]
                    ):
                        interactions[key]["lastPurchaseDate"] = order_date

            if not interactions:
                return {"saved_count": 0, "total_interactions": 0}

            # Prepare batch data
            batch_data = []
            for interaction in interactions.values():
                batch_data.append(
                    (
                        shop_id,
                        interaction["customerId"],
                        interaction["productId"],
                        interaction["purchaseCount"],
                        interaction["lastPurchaseDate"],
                        interaction["purchaseCount"] * 0.9,  # Simple time decay
                        now_utc(),
                    )
                )

            # Use Prisma's upsert method for each interaction feature to handle auto-generated IDs
            saved_count = 0
            for interaction_data in batch_data:
                try:
                    # Try to find existing record first
                    existing = await db.interactionfeatures.find_first(
                        where={
                            "shopId": interaction_data[0],
                            "customerId": interaction_data[1],
                            "productId": interaction_data[2],
                        }
                    )

                    if existing:
                        # Update existing record
                        await db.interactionfeatures.update(
                            where={"id": existing.id},
                            data={
                                "purchaseCount": interaction_data[3],
                                "lastPurchaseDate": interaction_data[4],
                                "timeDecayedWeight": interaction_data[5],
                                "lastComputedAt": interaction_data[6],
                            },
                        )
                    else:
                        # Create new record
                        await db.interactionfeatures.create(
                            data={
                                "shopId": interaction_data[0],
                                "customerId": interaction_data[1],
                                "productId": interaction_data[2],
                                "purchaseCount": interaction_data[3],
                                "lastPurchaseDate": interaction_data[4],
                                "timeDecayedWeight": interaction_data[5],
                                "lastComputedAt": interaction_data[6],
                            }
                        )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert interaction feature: {str(e)}")
                    continue

            return {
                "saved_count": saved_count,
                "total_interactions": len(interactions),
            }

        except Exception as e:
            logger.error(f"Failed to save interaction features batch: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    # Legacy methods (kept for backward compatibility but now use batch processing)

    async def _compute_and_save_product_features(
        self, shop_id: str, products: List[Dict], shop: Dict
    ) -> Dict[str, Any]:
        """Compute and save product features"""
        try:
            db = await self._get_database()
            saved_count = 0

            for product_data in products:
                # Convert to ShopifyProduct model
                product = self._convert_product_data(product_data)

                # Compute features
                features = await self.compute_product_features(product, shop)

                # Save to ProductFeatures table
                await db.execute_raw(
                    """
                    INSERT INTO "ProductFeatures" (
                        "shopId", "productId", "popularity", "priceTier", "category",
                        "variantComplexity", "imageRichness", "tagDiversity", 
                        "categoryEncoded", "vendorScore", "lastComputedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT ("shopId", "productId") 
                    DO UPDATE SET
                        "popularity" = EXCLUDED."popularity",
                        "priceTier" = EXCLUDED."priceTier", 
                        "category" = EXCLUDED."category",
                        "variantComplexity" = EXCLUDED."variantComplexity",
                        "imageRichness" = EXCLUDED."imageRichness",
                        "tagDiversity" = EXCLUDED."tagDiversity",
                        "categoryEncoded" = EXCLUDED."categoryEncoded",
                        "vendorScore" = EXCLUDED."vendorScore",
                        "lastComputedAt" = EXCLUDED."lastComputedAt"
                    """,
                    shop_id,
                    product.id,
                    features.get("total_orders", 0),
                    self._get_price_tier(features.get("avg_price", 0)),
                    product.product_type,
                    features.get("variant_count", 0) / 10.0,  # Normalize
                    features.get("image_count", 0) / 10.0,  # Normalize
                    features.get("tag_diversity", 0) / 10.0,  # Normalize
                    1 if product.product_type else 0,
                    1 if product.vendor else 0,
                    now_utc(),
                )
                saved_count += 1

            return {"saved_count": saved_count, "total_products": len(products)}

        except Exception as e:
            logger.error(f"Failed to save product features: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_customer_features(
        self,
        shop_id: str,
        customers: List[Dict],
        shop: Dict,
        orders: List[Dict],
        events: List[Dict],
    ) -> Dict[str, Any]:
        """Compute and save customer features"""
        try:
            db = await self._get_database()
            saved_count = 0

            for customer_data in customers:
                # Convert to ShopifyCustomer model
                customer = self._convert_customer_data(customer_data)

                # Get customer's orders and events
                customer_orders = [
                    o for o in orders if o.get("customerId") == customer.id
                ]
                customer_events = [
                    e for e in events if e.get("customerId") == customer.id
                ]

                # Compute features
                features = await self.compute_customer_features(
                    customer, shop, customer_orders, customer_events
                )

                # Save to UserFeatures table
                await db.execute_raw(
                    """
                    INSERT INTO "UserFeatures" (
                        "shopId", "customerId", "totalPurchases", "totalSpent",
                        "recencyDays", "avgPurchaseIntervalDays", "preferredCategory",
                        "lastComputedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT ("shopId", "customerId")
                    DO UPDATE SET
                        "totalPurchases" = EXCLUDED."totalPurchases",
                        "totalSpent" = EXCLUDED."totalSpent",
                        "recencyDays" = EXCLUDED."recencyDays",
                        "avgPurchaseIntervalDays" = EXCLUDED."avgPurchaseIntervalDays",
                        "preferredCategory" = EXCLUDED."preferredCategory",
                        "lastComputedAt" = EXCLUDED."lastComputedAt"
                    """,
                    shop_id,
                    customer.id,
                    features.get("total_orders", 0),
                    features.get("total_spent", 0),
                    features.get("days_since_creation", 0),
                    features.get("average_order_value", 0),
                    (
                        customer.default_address.country
                        if customer.default_address
                        else None
                    ),
                    now_utc(),
                )

                # Save to CustomerBehaviorFeatures table
                await db.execute_raw(
                    """
                    INSERT INTO "CustomerBehaviorFeatures" (
                        "shopId", "customerId", "eventDiversity", "eventFrequency",
                        "daysSinceFirstEvent", "daysSinceLastEvent", "purchaseFrequency",
                        "engagementScore", "recencyScore", "diversityScore", "behavioralScore",
                        "lastComputedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT ("shopId", "customerId")
                    DO UPDATE SET
                        "eventDiversity" = EXCLUDED."eventDiversity",
                        "eventFrequency" = EXCLUDED."eventFrequency",
                        "daysSinceFirstEvent" = EXCLUDED."daysSinceFirstEvent",
                        "daysSinceLastEvent" = EXCLUDED."daysSinceLastEvent",
                        "purchaseFrequency" = EXCLUDED."purchaseFrequency",
                        "engagementScore" = EXCLUDED."engagementScore",
                        "recencyScore" = EXCLUDED."recencyScore",
                        "diversityScore" = EXCLUDED."diversityScore",
                        "behavioralScore" = EXCLUDED."behavioralScore",
                        "lastComputedAt" = EXCLUDED."lastComputedAt"
                    """,
                    shop_id,
                    customer.id,
                    features.get("unique_event_types", 0),
                    features.get("event_count", 0),
                    features.get("days_since_creation", 0),
                    features.get("last_event_days", 0),
                    features.get("total_orders", 0),
                    features.get("engagement_score", 0),
                    features.get("recency_score", 0),
                    features.get("diversity_score", 0),
                    features.get("behavioral_score", 0),
                    now_utc(),
                )

                saved_count += 1

            return {"saved_count": saved_count, "total_customers": len(customers)}

        except Exception as e:
            logger.error(f"Failed to save customer features: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_collection_features(
        self, shop_id: str, collections: List[Dict], shop: Dict, products: List[Dict]
    ) -> Dict[str, Any]:
        """Compute and save collection features"""
        try:
            db = await self._get_database()
            saved_count = 0

            for collection_data in collections:
                # Convert to ShopifyCollection model
                collection = self._convert_collection_data(collection_data)

                # Compute features
                features = await self.compute_collection_features(
                    collection, shop, products
                )

                # Save to CollectionFeatures table
                await db.execute_raw(
                    """
                    INSERT INTO "CollectionFeatures" (
                        "shopId", "collectionId", "productCount", "isAutomated",
                        "performanceScore", "seoScore", "imageScore", "lastComputedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT ("shopId", "collectionId")
                    DO UPDATE SET
                        "productCount" = EXCLUDED."productCount",
                        "isAutomated" = EXCLUDED."isAutomated",
                        "performanceScore" = EXCLUDED."performanceScore",
                        "seoScore" = EXCLUDED."seoScore",
                        "imageScore" = EXCLUDED."imageScore",
                        "lastComputedAt" = EXCLUDED."lastComputedAt"
                    """,
                    shop_id,
                    collection.id,
                    features.get("products_count", 0),
                    features.get("is_automated", False),
                    features.get("performance_score", 0),
                    features.get("seo_score", 0),
                    features.get("image_score", 0),
                    now_utc(),
                )

                saved_count += 1

            return {"saved_count": saved_count, "total_collections": len(collections)}

        except Exception as e:
            logger.error(f"Failed to save collection features: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    async def _compute_and_save_interaction_features(
        self, shop_id: str, orders: List[Dict], products: List[Dict]
    ) -> Dict[str, Any]:
        """Compute and save interaction features"""
        try:
            db = await self._get_database()
            saved_count = 0

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
                    order_date = order.created_at
                    if order_date and (
                        not interactions[key]["lastPurchaseDate"]
                        or order_date > interactions[key]["lastPurchaseDate"]
                    ):
                        interactions[key]["lastPurchaseDate"] = order_date

            # Save interactions
            for interaction in interactions.values():
                await db.execute_raw(
                    """
                    INSERT INTO "InteractionFeatures" (
                        "shopId", "customerId", "productId", "purchaseCount",
                        "lastPurchaseDate", "timeDecayedWeight", "lastComputedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT ("shopId", "customerId", "productId")
                    DO UPDATE SET
                        "purchaseCount" = EXCLUDED."purchaseCount",
                        "lastPurchaseDate" = EXCLUDED."lastPurchaseDate",
                        "timeDecayedWeight" = EXCLUDED."timeDecayedWeight",
                        "lastComputedAt" = EXCLUDED."lastComputedAt"
                    """,
                    shop_id,
                    interaction["customerId"],
                    interaction["productId"],
                    interaction["purchaseCount"],
                    interaction["lastPurchaseDate"],
                    interaction["purchaseCount"] * 0.9,  # Simple time decay
                    now_utc(),
                )
                saved_count += 1

            return {"saved_count": saved_count, "total_interactions": len(interactions)}

        except Exception as e:
            logger.error(f"Failed to save interaction features: {str(e)}")
            return {"saved_count": 0, "error": str(e)}

    # Helper methods for data conversion

    def _convert_shop_data(self, shop_data: Dict) -> ShopifyShop:
        """Convert database shop data to ShopifyShop model"""
        # Extract domain from shopDomain and create myshopify_domain
        shop_domain = shop_data.get("shopDomain", "")
        myshopify_domain = (
            shop_domain
            if shop_domain.endswith(".myshopify.com")
            else f"{shop_domain}.myshopify.com"
        )

        return ShopifyShop(
            id=shop_data["id"],
            name=shop_data.get("shopDomain", "Unknown Shop"),
            domain=shop_domain,
            email=shop_data.get("email"),
            phone=None,
            access_token=shop_data.get("accessToken"),
            address1=None,
            address2=None,
            city=None,
            province=None,
            country=None,
            zip=None,
            currency=shop_data.get("currencyCode", "USD"),
            primary_locale="en",  # Default value
            timezone=None,
            plan_name=shop_data.get("planType"),
            plan_display_name=shop_data.get("planType"),
            shop_owner=None,
            has_storefront=False,
            has_discounts=False,
            has_gift_cards=False,
            has_marketing=False,
            has_multi_location=False,
            google_analytics_account=None,
            google_analytics_domain=None,
            seo_title=None,
            seo_description=None,
            meta_description=None,
            facebook_account=None,
            instagram_account=None,
            twitter_account=None,
            myshopify_domain=myshopify_domain,
            primary_location_id=None,
            created_at=shop_data.get("createdAt", now_utc()),
            updated_at=shop_data.get("updatedAt", now_utc()),
            bb_installed_at=None,
            bb_last_sync=None,
            bb_sync_frequency="daily",
            bb_ml_enabled=True,
            raw_data=shop_data,
        )

    def _convert_product_data(self, product_data: Dict) -> ShopifyProduct:
        """Convert database product data to ShopifyProduct model"""
        return ShopifyProduct(
            id=product_data["productId"],
            title=product_data.get("title", ""),
            handle=product_data.get("handle", ""),
            body_html=product_data.get("descriptionHtml", ""),
            product_type=product_data.get("productType", ""),
            vendor=product_data.get("vendor", ""),
            tags=product_data.get("tags", []),
            status=product_data.get("status", "active").lower(),
            price=product_data.get("price", 0),
            compare_at_price=product_data.get("compareAtPrice"),
            total_inventory=product_data.get("totalInventory", 0),
            main_image_url=product_data.get("imageUrl"),
            variant_count=len(product_data.get("variants") or []),
            has_multiple_variants=len(product_data.get("variants") or []) > 1,
            tag_count=len(product_data.get("tags") or []),
            collection_count=len(product_data.get("collections") or []),
            has_images=bool(product_data.get("imageUrl")),
            image_count=len(product_data.get("images") or []),
            is_published=product_data.get("isActive", False),
            created_at=product_data.get("productCreatedAt") or now_utc(),
            updated_at=product_data.get("productUpdatedAt") or now_utc(),
            published_at=product_data.get("productCreatedAt") or now_utc(),
            variants=[],  # Simplified for now
            images=[],  # Simplified for now
            options=[],  # Simplified for now
            metafields=[],  # Simplified for now
        )

    def _convert_customer_data(self, customer_data: Dict) -> ShopifyCustomer:
        """Convert database customer data to ShopifyCustomer model"""
        return ShopifyCustomer(
            id=customer_data["customerId"],
            email=customer_data.get("email", ""),
            first_name=customer_data.get("firstName", ""),
            last_name=customer_data.get("lastName", ""),
            phone=customer_data.get("phone"),
            orders_count=customer_data.get("ordersCount", 0),
            total_spent=customer_data.get("totalSpent", 0),
            verified_email=customer_data.get("emailVerified", False),
            accepts_marketing=customer_data.get("acceptsMarketing", False),
            tags=customer_data.get("tags", []),
            created_at=customer_data.get("customerCreatedAt") or now_utc(),
            updated_at=customer_data.get("customerUpdatedAt") or now_utc(),
            default_address=None,  # Simplified for now
            addresses=[],  # Simplified for now
        )

    def _convert_order_data(self, order_data: Dict) -> ShopifyOrder:
        """Convert database order data to ShopifyOrder model"""
        return ShopifyOrder(
            id=order_data["orderId"],
            customer_id=order_data.get("customerId"),
            total_price=order_data.get("totalPrice", 0),
            subtotal_price=order_data.get("subtotalPrice", 0),
            total_tax=order_data.get("totalTax", 0),
            total_discounts=order_data.get("totalDiscounts", 0),
            total_shipping_price_set=order_data.get("totalShippingPriceSet", 0),
            net_payment_refunded=order_data.get("netPaymentRefunded", 0),
            currency=order_data.get("currency", ""),
            financial_status=order_data.get("financialStatus", ""),
            fulfillment_status=order_data.get("fulfillmentStatus", ""),
            created_at=order_data.get("orderCreatedAt") or now_utc(),
            updated_at=order_data.get("orderUpdatedAt") or now_utc(),
            line_items=[],  # Simplified for now
            customer_orders_count=0,  # Not available
        )

    def _convert_collection_data(self, collection_data: Dict) -> ShopifyCollection:
        """Convert database collection data to ShopifyCollection model"""
        return ShopifyCollection(
            id=collection_data["collectionId"],
            title=collection_data.get("title", ""),
            handle=collection_data.get("handle", ""),
            body_html=collection_data.get("descriptionHtml", ""),
            products_count=collection_data.get("productsCount", 0),
            is_published=collection_data.get("isPublished", False),
            is_automated=collection_data.get("isAutomated", False),
            is_manual=not collection_data.get("isAutomated", True),
            sort_order=collection_data.get("sortOrder", ""),
            seo_title=collection_data.get("seoTitle"),
            seo_description=collection_data.get("seoDescription"),
            created_at=collection_data.get("collectionCreatedAt") or now_utc(),
            updated_at=collection_data.get("collectionUpdatedAt") or now_utc(),
            product_ids=collection_data.get("productIds", []),
        )

    def _convert_event_data(self, event_data: Dict) -> ShopifyCustomerEvent:
        """Convert database event data to ShopifyCustomerEvent model"""
        return ShopifyCustomerEvent(
            id=event_data["eventId"],
            customer_id=event_data.get("customerId"),
            event_type=event_data.get("eventType", ""),
            created_at=event_data.get("eventCreatedAt") or now_utc(),
            properties=event_data.get("properties", {}),
        )

    def _get_price_tier(self, price: float) -> str:
        """Convert price to tier"""
        if price < 25:
            return "low"
        elif price < 100:
            return "mid"
        else:
            return "high"
