"""
Business Metrics model for BetterBundle Python Worker
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class BusinessMetrics(BaseModel):
    """Business metrics and KPIs for a shop"""

    # Core identification
    id: str = Field(..., description="Unique metrics ID")
    shop_id: str = Field(..., description="Shop ID these metrics belong to")
    period_start: datetime = Field(..., description="Start of metrics period")
    period_end: datetime = Field(..., description="End of metrics period")
    period_type: str = Field(
        ..., description="Period type (daily, weekly, monthly, quarterly)"
    )

    # Revenue metrics
    total_revenue: float = Field(0.0, description="Total revenue in period")
    total_orders: int = Field(0, description="Total orders in period")
    average_order_value: float = Field(0.0, description="Average order value")
    revenue_growth_rate: Optional[float] = Field(
        None, description="Revenue growth rate vs previous period"
    )

    # Customer metrics
    total_customers: int = Field(0, description="Total unique customers")
    new_customers: int = Field(0, description="New customers in period")
    returning_customers: int = Field(0, description="Returning customers in period")
    customer_acquisition_cost: Optional[float] = Field(
        None, description="Customer acquisition cost"
    )
    customer_lifetime_value: Optional[float] = Field(
        None, description="Average customer lifetime value"
    )

    # Product metrics
    total_products: int = Field(0, description="Total active products")
    products_sold: int = Field(0, description="Products sold in period")
    top_selling_products: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top selling products"
    )
    low_stock_products: int = Field(0, description="Products with low stock")

    # Collection metrics
    total_collections: int = Field(0, description="Total collections")
    collection_performance: Dict[str, float] = Field(
        default_factory=dict, description="Collection performance scores"
    )

    # Conversion metrics
    conversion_rate: Optional[float] = Field(
        None, description="Overall conversion rate"
    )
    cart_abandonment_rate: Optional[float] = Field(
        None, description="Cart abandonment rate"
    )
    checkout_completion_rate: Optional[float] = Field(
        None, description="Checkout completion rate"
    )

    # Inventory metrics
    total_inventory_value: float = Field(0.0, description="Total inventory value")
    inventory_turnover_rate: Optional[float] = Field(
        None, description="Inventory turnover rate"
    )
    stockout_incidents: int = Field(0, description="Stockout incidents in period")

    # Marketing metrics
    marketing_spend: Optional[float] = Field(
        None, description="Marketing spend in period"
    )
    marketing_roi: Optional[float] = Field(
        None, description="Marketing return on investment"
    )
    email_open_rate: Optional[float] = Field(
        None, description="Email marketing open rate"
    )
    social_media_engagement: Optional[float] = Field(
        None, description="Social media engagement rate"
    )

    # Performance metrics
    website_traffic: Optional[int] = Field(
        None, description="Website traffic in period"
    )
    mobile_traffic_percentage: Optional[float] = Field(
        None, description="Percentage of mobile traffic"
    )
    page_load_time: Optional[float] = Field(None, description="Average page load time")

    # ML and AI metrics
    ml_recommendations_accuracy: Optional[float] = Field(
        None, description="ML recommendation accuracy"
    )
    ai_generated_revenue: Optional[float] = Field(
        None, description="Revenue from AI recommendations"
    )
    personalization_effectiveness: Optional[float] = Field(
        None, description="Personalization effectiveness score"
    )

    # Timestamps
    computed_at: datetime = Field(
        default_factory=now_utc, description="When metrics were computed"
    )
    created_at: datetime = Field(
        default_factory=now_utc, description="Metrics creation date"
    )
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @property
    def period_duration_days(self) -> int:
        """Get period duration in days"""
        return (self.period_end - self.period_start).days

    @property
    def revenue_per_day(self) -> float:
        """Get average revenue per day"""
        if self.period_duration_days == 0:
            return 0.0
        return self.total_revenue / self.period_duration_days

    @property
    def orders_per_day(self) -> float:
        """Get average orders per day"""
        if self.period_duration_days == 0:
            return 0.0
        return self.total_orders / self.period_duration_days

    @property
    def customer_retention_rate(self) -> Optional[float]:
        """Get customer retention rate"""
        if self.total_customers == 0:
            return None
        return (self.returning_customers / self.total_customers) * 100

    @property
    def profit_margin(self) -> Optional[float]:
        """Get profit margin (if cost data available)"""
        # This would need cost data to be implemented
        return None

    @property
    def is_current_period(self) -> bool:
        """Check if this is the current period"""
        return self.period_end >= now_utc()

    @property
    def period_age_days(self) -> int:
        """Get age of metrics period in days"""
        return (now_utc() - self.period_end).days

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of key metrics"""
        return {
            "period": f"{self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            "period_type": self.period_type,
            "total_revenue": self.total_revenue,
            "total_orders": self.total_orders,
            "average_order_value": self.average_order_value,
            "total_customers": self.total_customers,
            "new_customers": self.new_customers,
            "conversion_rate": self.conversion_rate,
            "revenue_growth_rate": self.revenue_growth_rate,
        }

    def get_performance_indicators(self) -> Dict[str, Any]:
        """Get performance indicators for dashboard"""
        return {
            "revenue_metrics": {
                "total_revenue": self.total_revenue,
                "revenue_per_day": self.revenue_per_day,
                "revenue_growth_rate": self.revenue_growth_rate,
            },
            "customer_metrics": {
                "total_customers": self.total_customers,
                "new_customers": self.new_customers,
                "customer_retention_rate": self.customer_retention_rate,
                "customer_lifetime_value": self.customer_lifetime_value,
            },
            "operational_metrics": {
                "total_orders": self.total_orders,
                "orders_per_day": self.orders_per_day,
                "average_order_value": self.average_order_value,
                "conversion_rate": self.conversion_rate,
            },
            "inventory_metrics": {
                "total_products": self.total_products,
                "total_inventory_value": self.total_inventory_value,
                "low_stock_products": self.low_stock_products,
            },
        }

    def get_growth_metrics(self) -> Dict[str, Any]:
        """Get growth-related metrics"""
        return {
            "revenue_growth": self.revenue_growth_rate,
            "customer_growth": self.new_customers,
            "order_growth": self.total_orders,
            "product_growth": self.total_products,
        }

    def get_ml_insights(self) -> Dict[str, Any]:
        """Get ML and AI related insights"""
        return {
            "ml_recommendations_accuracy": self.ml_recommendations_accuracy,
            "ai_generated_revenue": self.ai_generated_revenue,
            "personalization_effectiveness": self.personalization_effectiveness,
            "recommendation_impact": self._calculate_recommendation_impact(),
        }

    def _calculate_recommendation_impact(self) -> Optional[float]:
        """Calculate the impact of recommendations on revenue"""
        if self.ai_generated_revenue is None or self.total_revenue == 0:
            return None
        return (self.ai_generated_revenue / self.total_revenue) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()

    def to_dashboard_format(self) -> Dict[str, Any]:
        """Convert to dashboard format"""
        return {
            "summary": self.get_summary(),
            "performance_indicators": self.get_performance_indicators(),
            "growth_metrics": self.get_growth_metrics(),
            "ml_insights": self.get_ml_insights(),
            "metadata": {
                "id": self.id,
                "shop_id": self.shop_id,
                "computed_at": self.computed_at.isoformat(),
                "period_duration_days": self.period_duration_days,
                "is_current_period": self.is_current_period,
            },
        }
