"""
Feature engineering service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

# Removed Pydantic model imports - using dictionary data directly


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
        shop: Dict[str, Any],
        products: Optional[List[Dict[str, Any]]] = None,
        orders: Optional[List[Dict[str, Any]]] = None,
        customers: Optional[List[Dict[str, Any]]] = None,
        collections: Optional[List[Dict[str, Any]]] = None,
        behavioral_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Comprehensive feature computation for all entities in a shop

        Args:
            shop: Shop data as dictionary
            products: Optional list of product dictionaries
            orders: Optional list of order dictionaries
            customers: Optional list of customer dictionaries
            collections: Optional list of collection dictionaries
            behavioral_events: Optional list of event dictionaries

        Returns:
            Dictionary of all computed features by entity type
        """
        pass
