"""
Customer analytics service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class ICustomerAnalyticsService(ABC):
    """Interface for customer analytics and insights"""

    @abstractmethod
    async def analyze_customer_segments(self, shop_id: str) -> Dict[str, Any]:
        """Analyze customer segmentation"""
        pass

    @abstractmethod
    async def analyze_customer_lifetime_value(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze customer lifetime value metrics"""
        pass

    @abstractmethod
    async def analyze_customer_behavior(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze customer behavior patterns"""
        pass

    @abstractmethod
    async def analyze_customer_retention(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze customer retention metrics"""
        pass

    @abstractmethod
    async def analyze_customer_acquisition(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze customer acquisition metrics"""
        pass

    @abstractmethod
    async def identify_high_value_customers(self, shop_id: str) -> List[Dict[str, Any]]:
        """Identify high-value customers"""
        pass

    @abstractmethod
    async def predict_customer_churn(self, shop_id: str) -> List[Dict[str, Any]]:
        """Predict customer churn risk"""
        pass

    @abstractmethod
    async def get_customer_insights(self, shop_id: str) -> Dict[str, Any]:
        """Get comprehensive customer insights"""
        pass
