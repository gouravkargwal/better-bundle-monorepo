"""
Performance analytics service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class IPerformanceAnalyticsService(ABC):
    """Interface for performance analytics and optimization insights"""

    @abstractmethod
    async def analyze_shop_performance(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze overall shop performance"""
        pass

    @abstractmethod
    async def analyze_product_performance(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze product performance metrics"""
        pass

    @abstractmethod
    async def analyze_customer_performance(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze customer performance and behavior"""
        pass

    @abstractmethod
    async def analyze_marketing_performance(
        self, shop_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze marketing campaign performance"""
        pass

    @abstractmethod
    async def identify_performance_bottlenecks(
        self, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks and issues"""
        pass

    @abstractmethod
    async def generate_optimization_recommendations(
        self, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Generate optimization recommendations"""
        pass

    @abstractmethod
    async def track_performance_trends(
        self, shop_id: str, metric_name: str, days: int = 90
    ) -> Dict[str, Any]:
        """Track performance trends over time"""
        pass

    @abstractmethod
    async def benchmark_performance(
        self, shop_id: str, industry_benchmarks: Dict[str, float]
    ) -> Dict[str, Any]:
        """Benchmark performance against industry standards"""
        pass

    @abstractmethod
    async def get_performance_alerts(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get performance alerts and notifications"""
        pass
