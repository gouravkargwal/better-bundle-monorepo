"""
Revenue analytics service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class IRevenueAnalyticsService(ABC):
    """Interface for revenue analytics and insights"""
    
    @abstractmethod
    async def analyze_revenue_trends(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze revenue trends over time"""
        pass
    
    @abstractmethod
    async def analyze_revenue_by_source(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze revenue by source/channel"""
        pass
    
    @abstractmethod
    async def analyze_revenue_by_product(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze revenue by product"""
        pass
    
    @abstractmethod
    async def analyze_revenue_by_customer(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze revenue by customer segment"""
        pass
    
    @abstractmethod
    async def analyze_profit_margins(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze profit margins and profitability"""
        pass
    
    @abstractmethod
    async def forecast_revenue(
        self, 
        shop_id: str, 
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """Forecast future revenue"""
        pass
    
    @abstractmethod
    async def analyze_seasonal_patterns(
        self, 
        shop_id: str, 
        year: int
    ) -> Dict[str, Any]:
        """Analyze seasonal revenue patterns"""
        pass
    
    @abstractmethod
    async def get_revenue_insights(
        self, 
        shop_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive revenue insights"""
        pass
