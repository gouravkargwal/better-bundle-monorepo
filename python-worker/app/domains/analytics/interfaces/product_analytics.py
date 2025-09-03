"""
Product analytics service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class IProductAnalyticsService(ABC):
    """Interface for product analytics and insights"""
    
    @abstractmethod
    async def analyze_product_performance(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze overall product performance"""
        pass
    
    @abstractmethod
    async def analyze_product_sales(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze product sales metrics"""
        pass
    
    @abstractmethod
    async def analyze_product_inventory(
        self, 
        shop_id: str
    ) -> Dict[str, Any]:
        """Analyze product inventory metrics"""
        pass
    
    @abstractmethod
    async def identify_top_products(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Identify top-performing products"""
        pass
    
    @abstractmethod
    async def identify_underperforming_products(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Identify underperforming products"""
        pass
    
    @abstractmethod
    async def analyze_product_categories(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze product category performance"""
        pass
    
    @abstractmethod
    async def analyze_product_trends(
        self, 
        shop_id: str, 
        product_id: str, 
        days: int = 90
    ) -> Dict[str, Any]:
        """Analyze trends for a specific product"""
        pass
    
    @abstractmethod
    async def get_product_recommendations(
        self, 
        shop_id: str
    ) -> List[Dict[str, Any]]:
        """Get product optimization recommendations"""
        pass
