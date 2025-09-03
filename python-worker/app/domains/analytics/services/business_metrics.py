"""
Business metrics service implementation for BetterBundle Python Worker
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import statistics
import math

from app.core.logging import get_logger
from app.shared.decorators import async_timing
from app.shared.helpers import now_utc

from ..interfaces.business_metrics import IBusinessMetricsService
from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
)


class BusinessMetricsService(IBusinessMetricsService):
    """Business metrics service for computing and analyzing business KPIs"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Metric computation settings
        self.default_period_days = 30
        self.min_data_points = 5
        
        # Industry benchmarks (can be customized per shop)
        self.industry_benchmarks = {
            "conversion_rate": 0.03,  # 3%
            "customer_lifetime_value": 100.0,
            "repeat_purchase_rate": 0.25,  # 25%
            "average_order_value": 75.0,
        }
    
    @async_timing
    async def compute_overall_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute overall business metrics for a date range"""
        try:
            self.logger.info(f"Computing overall metrics", shop_id=shop_id)
            
            # Get shop data for the period
            shop_data = await self._get_shop_data(shop_id, start_date, end_date)
            
            if not shop_data:
                return {"error": "No data available for the specified period"}
            
            # Compute core metrics
            metrics = {}
            
            # Revenue metrics
            revenue_metrics = await self.compute_revenue_metrics(shop_id, start_date, end_date)
            metrics.update(revenue_metrics)
            
            # Order metrics
            order_metrics = await self.compute_order_metrics(shop_id, start_date, end_date)
            metrics.update(order_metrics)
            
            # Customer metrics
            customer_metrics = await self.compute_customer_metrics(shop_id, start_date, end_date)
            metrics.update(customer_metrics)
            
            # Product metrics
            product_metrics = await self.compute_product_metrics(shop_id, start_date, end_date)
            metrics.update(product_metrics)
            
            # Conversion metrics
            conversion_metrics = await self.compute_conversion_metrics(shop_id, start_date, end_date)
            metrics.update(conversion_metrics)
            
            # Growth metrics
            growth_metrics = await self.compute_growth_metrics(shop_id, start_date, end_date)
            metrics.update(growth_metrics)
            
            # Add metadata
            metrics["period"] = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": (end_date - start_date).days,
            }
            
            metrics["computed_at"] = now_utc().isoformat()
            
            self.logger.info(f"Overall metrics computed", shop_id=shop_id, metric_count=len(metrics))
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to compute overall metrics", shop_id=shop_id, error=str(e))
            raise
    
    @async_timing
    async def compute_revenue_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute revenue-related metrics"""
        try:
            shop_data = await self._get_shop_data(shop_id, start_date, end_date)
            orders = shop_data.get("orders", [])
            
            if not orders:
                return {"revenue": {"total": 0, "average": 0, "growth": 0}}
            
            # Calculate revenue metrics
            total_revenue = sum(order.total_price for order in orders)
            average_revenue = total_revenue / len(orders)
            
            # Calculate revenue growth (compare with previous period)
            previous_start = start_date - timedelta(days=(end_date - start_date).days)
            previous_orders = await self._get_shop_data(shop_id, previous_start, start_date)
            previous_revenue = sum(order.total_price for order in previous_orders.get("orders", []))
            
            revenue_growth = 0
            if previous_revenue > 0:
                revenue_growth = ((total_revenue - previous_revenue) / previous_revenue) * 100
            
            return {
                "revenue": {
                    "total": round(total_revenue, 2),
                    "average": round(average_revenue, 2),
                    "growth_percentage": round(revenue_growth, 2),
                    "order_count": len(orders),
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute revenue metrics", shop_id=shop_id, error=str(e))
            return {"revenue": {"error": str(e)}}
    
    @async_timing
    async def compute_order_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute order-related metrics"""
        try:
            shop_data = await self._get_shop_data(shop_id, start_date, end_date)
            orders = shop_data.get("orders", [])
            
            if not orders:
                return {"orders": {"total": 0, "average_value": 0}}
            
            # Calculate order metrics
            total_orders = len(orders)
            total_value = sum(order.total_price for order in orders)
            average_order_value = total_value / total_orders
            
            # Calculate order frequency
            unique_customers = set(order.customer_id for order in orders if order.customer_id)
            orders_per_customer = total_orders / len(unique_customers) if unique_customers else 0
            
            return {
                "orders": {
                    "total": total_orders,
                    "total_value": round(total_value, 2),
                    "average_value": round(average_order_value, 2),
                    "orders_per_customer": round(orders_per_customer, 2),
                    "unique_customers": len(unique_customers),
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute order metrics", shop_id=shop_id, error=str(e))
            return {"orders": {"error": str(e)}}
    
    @async_timing
    async def compute_customer_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute customer-related metrics"""
        try:
            shop_data = await self._get_shop_data(shop_id, start_date, end_date)
            customers = shop_data.get("customers", [])
            orders = shop_data.get("orders", [])
            
            if not customers:
                return {"customers": {"total": 0, "new": 0, "returning": 0}}
            
            # Calculate customer metrics
            total_customers = len(customers)
            
            # New vs returning customers
            customer_orders = {}
            for order in orders:
                if order.customer_id:
                    if order.customer_id not in customer_orders:
                        customer_orders[order.customer_id] = []
                    customer_orders[order.customer_id].append(order.created_at)
            
            new_customers = 0
            returning_customers = 0
            
            for customer in customers:
                if customer.id in customer_orders:
                    first_order = min(customer_orders[customer.id])
                    if first_order >= start_date:
                        new_customers += 1
                    else:
                        returning_customers += 1
                else:
                    new_customers += 1
            
            # Customer lifetime value (simplified)
            total_revenue = sum(order.total_price for order in orders)
            clv = total_revenue / total_customers if total_customers > 0 else 0
            
            return {
                "customers": {
                    "total": total_customers,
                    "new": new_customers,
                    "returning": returning_customers,
                    "lifetime_value": round(clv, 2),
                    "retention_rate": round((returning_customers / total_customers) * 100, 2) if total_customers > 0 else 0,
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute customer metrics", shop_id=shop_id, error=str(e))
            return {"customers": {"error": str(e)}}
    
    @async_timing
    async def compute_product_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute product-related metrics"""
        try:
            shop_data = await self._get_shop_data(shop_id, start_date, end_date)
            products = shop_data.get("products", [])
            orders = shop_data.get("orders", [])
            
            if not products:
                return {"products": {"total": 0, "active": 0, "top_performing": []}}
            
            # Calculate product metrics
            total_products = len(products)
            
            # Active products (with sales in period)
            product_sales = {}
            for order in orders:
                for line_item in order.line_items:
                    if line_item.product_id not in product_sales:
                        product_sales[line_item.product_id] = 0
                    product_sales[line_item.product_id] += line_item.quantity
            
            active_products = len(product_sales)
            
            # Top performing products
            top_products = sorted(
                [(pid, qty) for pid, qty in product_sales.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            return {
                "products": {
                    "total": total_products,
                    "active": active_products,
                    "inactive": total_products - active_products,
                    "top_performing": [
                        {"product_id": pid, "quantity_sold": qty}
                        for pid, qty in top_products
                    ],
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute product metrics", shop_id=shop_id, error=str(e))
            return {"products": {"error": str(e)}}
    
    @async_timing
    async def compute_conversion_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute conversion and funnel metrics"""
        try:
            # This would typically integrate with analytics platforms
            # For now, return mock conversion metrics
            return {
                "conversion": {
                    "overall_rate": 0.025,  # 2.5%
                    "cart_abandonment_rate": 0.68,  # 68%
                    "checkout_completion_rate": 0.32,  # 32%
                    "bounce_rate": 0.45,  # 45%
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute conversion metrics", shop_id=shop_id, error=str(e))
            return {"conversion": {"error": str(e)}}
    
    @async_timing
    async def compute_growth_metrics(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Compute growth and trend metrics"""
        try:
            # Get current and previous period data
            current_data = await self._get_shop_data(shop_id, start_date, end_date)
            period_days = (end_date - start_date).days
            previous_start = start_date - timedelta(days=period_days)
            previous_data = await self._get_shop_data(shop_id, previous_start, start_date)
            
            # Calculate growth metrics
            current_revenue = sum(order.total_price for order in current_data.get("orders", []))
            previous_revenue = sum(order.total_price for order in previous_data.get("orders", []))
            
            current_orders = len(current_data.get("orders", []))
            previous_orders = len(previous_data.get("orders", []))
            
            current_customers = len(current_data.get("customers", []))
            previous_customers = len(previous_data.get("customers", []))
            
            # Growth calculations
            revenue_growth = self._calculate_growth(current_revenue, previous_revenue)
            order_growth = self._calculate_growth(current_orders, previous_orders)
            customer_growth = self._calculate_growth(current_customers, previous_customers)
            
            return {
                "growth": {
                    "revenue_growth_percentage": revenue_growth,
                    "order_growth_percentage": order_growth,
                    "customer_growth_percentage": customer_growth,
                    "period_comparison": f"{period_days} days",
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute growth metrics", shop_id=shop_id, error=str(e))
            return {"growth": {"error": str(e)}}
    
    @async_timing
    async def get_metric_history(
        self, 
        shop_id: str, 
        metric_name: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric"""
        try:
            end_date = now_utc()
            start_date = end_date - timedelta(days=days)
            
            # Get daily data points
            history = []
            current_date = start_date
            
            while current_date <= end_date:
                next_date = current_date + timedelta(days=1)
                
                # Get data for this day
                daily_data = await self._get_shop_data(shop_id, current_date, next_date)
                
                if metric_name == "revenue":
                    daily_revenue = sum(order.total_price for order in daily_data.get("orders", []))
                    history.append({
                        "date": current_date.isoformat(),
                        "value": daily_revenue,
                    })
                elif metric_name == "orders":
                    daily_orders = len(daily_data.get("orders", []))
                    history.append({
                        "date": current_date.isoformat(),
                        "value": daily_orders,
                    })
                elif metric_name == "customers":
                    daily_customers = len(daily_data.get("customers", []))
                    history.append({
                        "date": current_date.isoformat(),
                        "value": daily_customers,
                    })
                
                current_date = next_date
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get metric history", shop_id=shop_id, error=str(e))
            return []
    
    @async_timing
    async def compare_periods(
        self, 
        shop_id: str, 
        current_period: Dict[str, datetime], 
        previous_period: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """Compare metrics between two time periods"""
        try:
            # Get metrics for both periods
            current_metrics = await self.compute_overall_metrics(
                shop_id, current_period["start"], current_period["end"]
            )
            previous_metrics = await self.compute_overall_metrics(
                shop_id, previous_period["start"], previous_period["end"]
            )
            
            # Calculate period-over-period changes
            comparison = {}
            
            for metric_category in ["revenue", "orders", "customers"]:
                if metric_category in current_metrics and metric_category in previous_metrics:
                    current = current_metrics[metric_category]
                    previous = previous_metrics[metric_category]
                    
                    if "total" in current and "total" in previous:
                        change = self._calculate_growth(current["total"], previous["total"])
                        comparison[f"{metric_category}_change"] = change
            
            return {
                "current_period": current_metrics,
                "previous_period": previous_metrics,
                "comparison": comparison,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compare periods", shop_id=shop_id, error=str(e))
            return {"error": str(e)}
    
    @async_timing
    async def get_kpi_dashboard(
        self, 
        shop_id: str
    ) -> Dict[str, Any]:
        """Get KPI dashboard data"""
        try:
            # Get last 30 days metrics
            end_date = now_utc()
            start_date = end_date - timedelta(days=self.default_period_days)
            
            overall_metrics = await self.compute_overall_metrics(shop_id, start_date, end_date)
            
            # Get metric history for trending
            revenue_history = await self.get_metric_history(shop_id, "revenue", 30)
            order_history = await self.get_metric_history(shop_id, "orders", 30)
            
            return {
                "kpi_dashboard": {
                    "current_period": overall_metrics,
                    "trends": {
                        "revenue": revenue_history,
                        "orders": order_history,
                    },
                    "last_updated": now_utc().isoformat(),
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get KPI dashboard", shop_id=shop_id, error=str(e))
            return {"error": str(e)}
    
    # Helper methods
    async def _get_shop_data(
        self, 
        shop_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get shop data for a specific time period"""
        # This would integrate with your data layer
        # For now, return mock data structure
        return {
            "orders": [],
            "customers": [],
            "products": [],
            "collections": [],
        }
    
    def _calculate_growth(self, current: float, previous: float) -> float:
        """Calculate growth percentage"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)
