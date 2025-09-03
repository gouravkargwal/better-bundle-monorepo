"""
Analytics domain for BetterBundle Python Worker
"""

from .interfaces import (
    IBusinessMetricsService,
    IPerformanceAnalyticsService,
    ICustomerAnalyticsService,
    IProductAnalyticsService,
    IRevenueAnalyticsService,
)

from .services import (
    BusinessMetricsService,
    PerformanceAnalyticsService,
    CustomerAnalyticsService,
    ProductAnalyticsService,
    RevenueAnalyticsService,
)

__all__ = [
    # Interfaces
    "IBusinessMetricsService",
    "IPerformanceAnalyticsService", 
    "ICustomerAnalyticsService",
    "IProductAnalyticsService",
    "IRevenueAnalyticsService",
    
    # Services
    "BusinessMetricsService",
    "PerformanceAnalyticsService",
    "CustomerAnalyticsService", 
    "ProductAnalyticsService",
    "RevenueAnalyticsService",
]
