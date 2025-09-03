"""
Feature engineering service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    ShopifyCustomerEvent,
)
from app.domains.ml.models import MLFeatures


class IFeatureEngineeringService(ABC):
    """Interface for feature engineering operations"""

    @abstractmethod
    async def compute_product_features(
        self,
        product: ShopifyProduct,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
    ) -> Dict[str, Any]:
        """
        Compute ML features for a product

        Args:
            product: Product to compute features for
            shop: Shop context
            orders: Optional orders for historical data
            collections: Optional collections for context

        Returns:
            Dictionary of computed features
        """
        pass

    @abstractmethod
    async def compute_customer_features(
        self,
        customer: ShopifyCustomer,
        shop: ShopifyShop,
        orders: Optional[List[ShopifyOrder]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """
        Compute ML features for a customer

        Args:
            customer: Customer to compute features for
            shop: Shop context
            orders: Optional orders for historical data
            events: Optional customer events for behavior data

        Returns:
            Dictionary of computed features
        """
        pass

    @abstractmethod
    async def compute_order_features(
        self,
        order: ShopifyOrder,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """
        Compute ML features for an order

        Args:
            order: Order to compute features for
            shop: Shop context
            products: Optional products for context

        Returns:
            Dictionary of computed features
        """
        pass

    @abstractmethod
    async def compute_collection_features(
        self,
        collection: ShopifyCollection,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
    ) -> Dict[str, Any]:
        """
        Compute ML features for a collection

        Args:
            collection: Collection to compute features for
            shop: Shop context
            products: Optional products in collection

        Returns:
            Dictionary of computed features
        """
        pass

    @abstractmethod
    async def compute_shop_features(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        events: Optional[List[ShopifyCustomerEvent]] = None,
    ) -> Dict[str, Any]:
        """
        Compute ML features for a shop

        Args:
            shop: Shop to compute features for
            products: Optional products for context
            orders: Optional orders for context
            customers: Optional customers for context
            collections: Optional collections for context
            events: Optional events for context

        Returns:
            Dictionary of computed features
        """
        pass

    @abstractmethod
    async def compute_cross_entity_features(
        self,
        shop: ShopifyShop,
        products: List[ShopifyProduct],
        orders: List[ShopifyOrder],
        customers: List[ShopifyCustomer],
        collections: List[ShopifyCollection],
        events: List[ShopifyCustomerEvent],
    ) -> Dict[str, Any]:
        """
        Compute cross-entity ML features

        Args:
            shop: Shop context
            products: All products
            orders: All orders
            customers: All customers
            collections: All collections
            events: All customer events

        Returns:
            Dictionary of cross-entity features
        """
        pass

    @abstractmethod
    async def create_ml_features(
        self,
        shop_id: str,
        feature_type: str,
        entity_id: str,
        features: Dict[str, Any],
        data_sources: List[str],
    ) -> MLFeatures:
        """
        Create MLFeatures model instance

        Args:
            shop_id: Shop ID
            feature_type: Type of features
            entity_id: Entity ID
            features: Computed features
            data_sources: Data sources used

        Returns:
            MLFeatures instance
        """
        pass

    @abstractmethod
    async def validate_features(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, Any]:
        """
        Validate computed features

        Args:
            features: Features to validate
            feature_type: Type of features

        Returns:
            Validation results
        """
        pass

    @abstractmethod
    async def get_feature_schema(self, feature_type: str) -> Dict[str, Any]:
        """
        Get feature schema for a type

        Args:
            feature_type: Type of features

        Returns:
            Feature schema definition
        """
        pass

    @abstractmethod
    async def get_feature_importance(
        self, features: Dict[str, Any], feature_type: str
    ) -> Dict[str, float]:
        """
        Get feature importance scores

        Args:
            features: Features to analyze
            feature_type: Type of features

        Returns:
            Feature importance scores
        """
        pass

    @abstractmethod
    async def normalize_features(
        self,
        features: Dict[str, Any],
        feature_type: str,
        normalization_method: str = "standard",
    ) -> Dict[str, Any]:
        """
        Normalize features for ML training

        Args:
            features: Features to normalize
            feature_type: Type of features
            normalization_method: Normalization method

        Returns:
            Normalized features
        """
        pass

    @abstractmethod
    async def encode_categorical_features(
        self,
        features: Dict[str, Any],
        feature_type: str,
        encoding_method: str = "one_hot",
    ) -> Dict[str, Any]:
        """
        Encode categorical features

        Args:
            features: Features to encode
            feature_type: Type of features
            encoding_method: Encoding method

        Returns:
            Encoded features
        """
        pass

    @abstractmethod
    async def compute_feature_statistics(
        self, features_list: List[Dict[str, Any]], feature_type: str
    ) -> Dict[str, Any]:
        """
        Compute statistics across multiple feature sets

        Args:
            features_list: List of feature dictionaries
            feature_type: Type of features

        Returns:
            Feature statistics
        """
        pass
