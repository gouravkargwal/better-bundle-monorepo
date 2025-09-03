"""
Business metrics service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class IBusinessMetricsService(ABC):
    """Interface for business metrics computation and analysis"""
    
    @abstractmethod
    async def compute_overall_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute overall business metrics for a date range"""
        pass
    
    @abstractmethod
    async def compute_revenue_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute revenue-related metrics"""
        pass
    
    @abstractmethod
    async def compute_order_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute order-related metrics"""
        pass
    
    @abstractmethod
    async def compute_customer_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute customer-related metrics"""
        pass
    
    @abstractmethod
    async def compute_product_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute product-related metrics"""
        pass
    
    @abstractmethod
    async def compute_conversion_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute conversion and funnel metrics"""
        pass
    
    @abstractmethod
    async def compute_growth_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute growth and trend metrics"""
        pass
    
    @abstractmethod
    async def get_metric_history(
        self, 
        shop_id: str, 
        metric_name: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric"""
        pass
    
    @abstractmethod
    async def compare_periods(
        self, 
        shop_id: str, 
        current_period: Dict[str, datetime], 
        previous_period: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """Compare metrics between two time periods"""
        pass
    
    @abstractmethod
    async def get_kpi_dashboard(
        self, 
        shop_id: str
    ) -> Dict[str, Any]:
        """Get KPI dashboard data"""
        pass
