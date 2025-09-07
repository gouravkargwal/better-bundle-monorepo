"""
Feature engineering service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    BehavioralEvent,
)


class IFeatureEngineeringService(ABC):
    """Interface for feature engineering operations"""

    @abstractmethod
    async def run_comprehensive_pipeline_for_shop(
        self,
        shop_id: str,
        batch_size: int = 1000,
        incremental: bool = False,
    ) -> Dict[str, Any]:
        """
        Run comprehensive feature computation pipeline for a shop

        Args:
            shop_id: Shop ID to compute features for
            batch_size: Batch size for processing
            incremental: Whether to run incremental processing

        Returns:
            Dictionary with pipeline results
        """
        pass

    @abstractmethod
    async def compute_all_features_for_shop(
        self,
        shop: ShopifyShop,
        products: Optional[List[ShopifyProduct]] = None,
        orders: Optional[List[ShopifyOrder]] = None,
        customers: Optional[List[ShopifyCustomer]] = None,
        collections: Optional[List[ShopifyCollection]] = None,
        behavioral_events: Optional[List[BehavioralEvent]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Comprehensive feature computation for all entities in a shop

        Args:
            shop: Shop to compute features for
            products: Optional products
            orders: Optional orders
            customers: Optional customers
            collections: Optional collections
            behavioral_events: Optional events

        Returns:
            Dictionary of all computed features by entity type
        """
        pass
