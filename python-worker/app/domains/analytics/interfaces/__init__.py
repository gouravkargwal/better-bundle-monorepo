"""
Analytics interfaces for BetterBundle Python Worker
"""

from .business_metrics import IBusinessMetricsService
from .performance_analytics import IPerformanceAnalyticsService
from .customer_analytics import ICustomerAnalyticsService
from .product_analytics import IProductAnalyticsService
from .revenue_analytics import IRevenueAnalyticsService

__all__ = [
    "IBusinessMetricsService",
    "IPerformanceAnalyticsService",
    "ICustomerAnalyticsService", 
    "IProductAnalyticsService",
    "IRevenueAnalyticsService",
]
