"""
Heuristic service for determining when to run analysis based on shop data
"""

from app.core.logger import get_logger
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.core.database import get_database
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)


@dataclass
class HeuristicFactors:
    """Factors used to calculate next analysis time"""

    order_volume: float  # Orders per day
    revenue_velocity: float  # Revenue per day
    product_churn: float  # New/removed products percentage
    bundle_effectiveness: float  # Bundle performance score (0-1)
    data_change_rate: float  # Percentage of data changed
    seasonality: float  # Seasonal adjustment factor
    shop_activity_level: str  # 'low', 'medium', 'high'
    user_engagement: float  # User interaction with recommendations


@dataclass
class HeuristicResult:
    """Result of heuristic calculation"""

    next_analysis_hours: int
    factors: HeuristicFactors
    reasoning: List[str]
    confidence: float


class AnalysisHeuristicService:
    """Service for calculating when to run next analysis"""

    # Minimum and maximum intervals (1 day to 30 days)
    MIN_INTERVAL_HOURS = 24
    MAX_INTERVAL_HOURS = 24 * 30

    def __init__(self):
        self.db = None
        self.redis = None

    async def initialize(self):
        """Initialize database and Redis connections"""
        self.db = await get_database()
        self.redis = await get_redis_client()

    async def calculate_next_analysis_time(
        self, shop_id: str, analysis_result: Optional[Dict[str, Any]] = None
    ) -> HeuristicResult:
        """Calculate next analysis time based on current shop data"""
        try:

            # Gather all heuristic factors
            factors = await self._gather_heuristic_factors(shop_id, analysis_result)

            # Calculate individual intervals based on each factor
            intervals = self._calculate_factor_intervals(factors)

            # Apply weights and calculate weighted average
            weighted_interval = self._calculate_weighted_interval(intervals, factors)

            # Apply seasonal adjustments
            seasonal_interval = self._apply_seasonal_adjustment(
                weighted_interval, factors.seasonality
            )

            # Ensure within bounds (1-30 days)
            final_interval = self._clamp_interval(seasonal_interval)

            # Generate reasoning
            reasoning = self._generate_reasoning(intervals, factors, final_interval)

            # Calculate confidence score
            confidence = self._calculate_confidence(factors)

            result = HeuristicResult(
                next_analysis_hours=final_interval,
                factors=factors,
                reasoning=reasoning,
                confidence=confidence,
            )

            return result

        except Exception as e:
            logger.error("Error calculating heuristic", shop_id=shop_id, error=str(e))
            # Fallback to default 7 days
            return HeuristicResult(
                next_analysis_hours=24 * 7,
                factors=HeuristicFactors(
                    order_volume=0.0,
                    revenue_velocity=0.0,
                    product_churn=0.0,
                    bundle_effectiveness=0.0,
                    data_change_rate=0.0,
                    seasonality=1.0,
                    shop_activity_level="medium",
                    user_engagement=0.0,
                ),
                reasoning=[
                    "Fallback to default 7-day interval due to calculation error"
                ],
                confidence=0.5,
            )

    async def _gather_heuristic_factors(
        self, shop_id: str, analysis_result: Optional[Dict[str, Any]]
    ) -> HeuristicFactors:
        """Gather all heuristic factors for a shop"""
        # Get shop data
        shop = await self.db.shop.find_unique(where={"id": shop_id})
        if not shop:
            raise ValueError(f"Shop not found: {shop_id}")

        # Calculate factors in parallel
        order_volume = await self._calculate_order_volume(shop_id)
        revenue_velocity = await self._calculate_revenue_velocity(shop_id)
        product_churn = await self._calculate_product_churn(shop_id)
        bundle_effectiveness = self._calculate_bundle_effectiveness(analysis_result)
        data_change_rate = await self._calculate_data_change_rate(shop_id)
        user_engagement = await self._calculate_user_engagement(shop_id)
        seasonality = self._calculate_seasonality()
        shop_activity_level = self._determine_activity_level(
            order_volume, revenue_velocity
        )

        return HeuristicFactors(
            order_volume=order_volume,
            revenue_velocity=revenue_velocity,
            product_churn=product_churn,
            bundle_effectiveness=bundle_effectiveness,
            data_change_rate=data_change_rate,
            seasonality=seasonality,
            shop_activity_level=shop_activity_level,
            user_engagement=user_engagement,
        )

    async def _calculate_order_volume(self, shop_id: str) -> float:
        """Calculate average orders per day in last 30 days"""
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)

            # Count orders in last 30 days
            order_count = await self.db.orderdata.count(
                where={"shopId": shop_id, "orderDate": {"gte": thirty_days_ago}}
            )

            return order_count / 30.0
        except Exception as e:
            logger.error(
                "Error calculating order volume", shop_id=shop_id, error=str(e)
            )
            return 0.0

    async def _calculate_revenue_velocity(self, shop_id: str) -> float:
        """Calculate average revenue per day in last 30 days"""
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)

            # Sum revenue in last 30 days
            orders = await self.db.orderdata.find_many(
                where={"shopId": shop_id, "orderDate": {"gte": thirty_days_ago}},
                select={"totalAmount": True},
            )

            total_revenue = sum(order.totalAmount for order in orders)
            return total_revenue / 30.0
        except Exception as e:
            logger.error(
                "Error calculating revenue velocity", shop_id=shop_id, error=str(e)
            )
            return 0.0

    async def _calculate_product_churn(self, shop_id: str) -> float:
        """Calculate product churn rate"""
        try:
            # Get product counts over time
            total_products = await self.db.productdata.count(where={"shopId": shop_id})

            # For now, use a simple heuristic based on total products
            # In a real implementation, you'd track product additions/removals over time
            if total_products > 100:
                return 0.05  # 5% churn for large catalogs
            elif total_products > 50:
                return 0.03  # 3% churn for medium catalogs
            else:
                return 0.01  # 1% churn for small catalogs
        except Exception as e:
            logger.error(
                "Error calculating product churn", shop_id=shop_id, error=str(e)
            )
            return 0.0

    def _calculate_bundle_effectiveness(
        self, analysis_result: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate bundle effectiveness from analysis results"""
        if not analysis_result or not analysis_result.get("bundles"):
            return 0.5  # Default effectiveness

        bundles = analysis_result["bundles"]
        if not bundles:
            return 0.0

        # Calculate average confidence and lift
        total_confidence = sum(bundle.get("confidence", 0) for bundle in bundles)
        total_lift = sum(bundle.get("lift", 0) for bundle in bundles)

        avg_confidence = total_confidence / len(bundles)
        avg_lift = total_lift / len(bundles)

        # Combine confidence and lift for effectiveness score
        effectiveness = (avg_confidence * 0.6) + (min(avg_lift / 10, 1.0) * 0.4)

        return min(effectiveness, 1.0)

    async def _calculate_data_change_rate(self, shop_id: str) -> float:
        """Calculate data change rate"""
        try:
            # Get latest order timestamp
            latest_order = await self.db.orderdata.find_first(
                where={"shopId": shop_id},
                order={"orderDate": "desc"},
                select={"orderDate": True},
            )

            if not latest_order:
                return 0.0

            # Calculate days since last order
            days_since_order = (datetime.now() - latest_order.orderDate).days

            # Higher change rate for more recent activity
            if days_since_order <= 1:
                return 0.2  # 20% change rate for very recent activity
            elif days_since_order <= 7:
                return 0.1  # 10% change rate for recent activity
            else:
                return 0.05  # 5% change rate for older activity
        except Exception as e:
            logger.error(
                "Error calculating data change rate", shop_id=shop_id, error=str(e)
            )
            return 0.0

    async def _calculate_user_engagement(self, shop_id: str) -> float:
        """Calculate user engagement with recommendations"""
        try:
            # For now, use a simple heuristic based on shop activity
            # In a real implementation, you'd track widget interactions
            order_volume = await self._calculate_order_volume(shop_id)

            if order_volume > 20:
                return 0.8  # High engagement for active shops
            elif order_volume > 10:
                return 0.6  # Medium engagement
            elif order_volume > 5:
                return 0.4  # Low engagement
            else:
                return 0.2  # Very low engagement
        except Exception as e:
            logger.error(
                "Error calculating user engagement", shop_id=shop_id, error=str(e)
            )
            return 0.0

    def _calculate_seasonality(self) -> float:
        """Calculate seasonal adjustment factor"""
        # Simple seasonal adjustment based on month
        month = datetime.now().month

        # Holiday season (Nov-Dec) - more frequent analysis
        if month in [11, 12]:
            return 0.7  # 30% more frequent

        # Summer months (Jun-Aug) - less frequent analysis
        elif month in [6, 7, 8]:
            return 1.3  # 30% less frequent

        # Default
        else:
            return 1.0

    def _determine_activity_level(
        self, order_volume: float, revenue_velocity: float
    ) -> str:
        """Determine shop activity level"""
        if order_volume > 20 or revenue_velocity > 1000:
            return "high"
        elif order_volume > 10 or revenue_velocity > 500:
            return "medium"
        else:
            return "low"

    def _calculate_factor_intervals(
        self, factors: HeuristicFactors
    ) -> Dict[str, float]:
        """Calculate intervals based on individual factors"""
        intervals = {}

        # Order volume: more orders = more frequent analysis
        if factors.order_volume > 20:
            intervals["order_volume"] = 24 * 2  # 2 days
        elif factors.order_volume > 10:
            intervals["order_volume"] = 24 * 4  # 4 days
        elif factors.order_volume > 5:
            intervals["order_volume"] = 24 * 7  # 7 days
        else:
            intervals["order_volume"] = 24 * 14  # 14 days

        # Bundle effectiveness: better bundles = more frequent analysis
        if factors.bundle_effectiveness > 0.7:
            intervals["bundle_effectiveness"] = 24 * 3  # 3 days
        elif factors.bundle_effectiveness > 0.5:
            intervals["bundle_effectiveness"] = 24 * 7  # 7 days
        else:
            intervals["bundle_effectiveness"] = 24 * 14  # 14 days

        # Data change rate: more changes = more frequent analysis
        if factors.data_change_rate > 0.1:
            intervals["data_change_rate"] = 24 * 2  # 2 days
        elif factors.data_change_rate > 0.05:
            intervals["data_change_rate"] = 24 * 5  # 5 days
        else:
            intervals["data_change_rate"] = 24 * 10  # 10 days

        # User engagement: more engagement = more frequent analysis
        if factors.user_engagement > 0.6:
            intervals["user_engagement"] = 24 * 4  # 4 days
        elif factors.user_engagement > 0.3:
            intervals["user_engagement"] = 24 * 7  # 7 days
        else:
            intervals["user_engagement"] = 24 * 14  # 14 days

        return intervals

    def _calculate_weighted_interval(
        self, intervals: Dict[str, float], factors: HeuristicFactors
    ) -> float:
        """Calculate weighted average interval"""
        weights = {
            "order_volume": 0.3,
            "bundle_effectiveness": 0.3,
            "data_change_rate": 0.2,
            "user_engagement": 0.2,
        }

        weighted_sum = sum(
            intervals[key] * weights[key] for key in weights if key in intervals
        )
        return weighted_sum

    def _apply_seasonal_adjustment(self, interval: float, seasonality: float) -> float:
        """Apply seasonal adjustment to interval"""
        return interval * seasonality

    def _clamp_interval(self, interval: float) -> int:
        """Clamp interval to min/max bounds"""
        return max(self.MIN_INTERVAL_HOURS, min(self.MAX_INTERVAL_HOURS, int(interval)))

    def _generate_reasoning(
        self,
        intervals: Dict[str, float],
        factors: HeuristicFactors,
        final_interval: int,
    ) -> List[str]:
        """Generate reasoning for the calculated interval"""
        reasoning = []

        # Add reasoning for each factor
        if factors.order_volume > 20:
            reasoning.append(
                f"High order volume ({factors.order_volume:.1f} orders/day) suggests frequent analysis"
            )
        elif factors.order_volume < 5:
            reasoning.append(
                f"Low order volume ({factors.order_volume:.1f} orders/day) allows less frequent analysis"
            )

        if factors.bundle_effectiveness > 0.7:
            reasoning.append(
                f"High bundle effectiveness ({(factors.bundle_effectiveness * 100):.0f}%) - running analysis more frequently"
            )
        elif factors.bundle_effectiveness < 0.3:
            reasoning.append(
                f"Low bundle effectiveness ({(factors.bundle_effectiveness * 100):.0f}%) - less frequent analysis needed"
            )

        if factors.data_change_rate > 0.1:
            reasoning.append(
                f"High data change rate ({(factors.data_change_rate * 100):.0f}%) requires frequent updates"
            )

        if factors.seasonality != 1.0:
            reasoning.append(
                f"Seasonal adjustment applied ({factors.seasonality:.2f}x frequency)"
            )

        reasoning.append(f"Final interval: {(final_interval / 24):.1f} days")

        return reasoning

    def _calculate_confidence(self, factors: HeuristicFactors) -> float:
        """Calculate confidence in the heuristic decision"""
        confidence = 0.5  # Base confidence

        # Higher confidence with more data
        if factors.order_volume > 10:
            confidence += 0.2
        if factors.user_engagement > 0.1:
            confidence += 0.1
        if factors.bundle_effectiveness > 0.5:
            confidence += 0.1
        if factors.data_change_rate > 0.05:
            confidence += 0.1

        return min(confidence, 1.0)

    async def store_heuristic_decision(
        self,
        shop_id: str,
        heuristic_result: HeuristicResult,
        analysis_result: Optional[Dict[str, Any]],
    ):
        """Store heuristic decision for learning"""
        try:
            await self.db.heuristicdecision.create(
                data={
                    "shopId": shop_id,
                    "predictedInterval": heuristic_result.next_analysis_hours,
                    "factors": heuristic_result.factors.__dict__,
                    "reasoning": heuristic_result.reasoning,
                    "confidence": heuristic_result.confidence,
                    "analysisResult": analysis_result or {},
                }
            )
        except Exception as e:
            logger.error(
                "Error storing heuristic decision", shop_id=shop_id, error=str(e)
            )

    async def get_shops_due_for_analysis(self) -> List[Dict[str, Any]]:
        """Get all shops that are due for analysis"""
        try:
            now = datetime.now()

            # Get all shops with analysis configs
            shops = await self.db.shopanalysisconfig.find_many(
                where={
                    "autoAnalysisEnabled": True,
                    "nextScheduledAnalysis": {"lte": now},
                },
                include={
                    "shop": {
                        "select": {
                            "id": True,
                            "shopId": True,
                            "shopDomain": True,
                            "accessToken": True,
                        }
                    }
                },
            )

            return shops

        except Exception as e:
            logger.error("Error getting shops due for analysis", error=str(e))
            return []

    async def schedule_next_analysis(
        self, shop_id: str, analysis_result: Optional[Dict[str, Any]] = None
    ):
        """Schedule next analysis for a shop"""
        try:
            # Calculate next analysis time
            heuristic_result = await self.calculate_next_analysis_time(
                shop_id, analysis_result
            )

            # Calculate next scheduled time
            next_scheduled_time = datetime.now() + timedelta(
                hours=heuristic_result.next_analysis_hours
            )

            # Update or create shop analysis config
            await self.db.shopanalysisconfig.upsert(
                where={"shopId": shop_id},
                data={
                    "update": {
                        "lastAnalysisAt": datetime.now(),
                        "nextScheduledAnalysis": next_scheduled_time,
                        "heuristicFactors": heuristic_result.factors.__dict__,
                        "lastHeuristicResult": {
                            "nextAnalysisHours": heuristic_result.next_analysis_hours,
                            "reasoning": heuristic_result.reasoning,
                            "confidence": heuristic_result.confidence,
                        },
                    },
                    "create": {
                        "shopId": shop_id,
                        "lastAnalysisAt": datetime.now(),
                        "nextScheduledAnalysis": next_scheduled_time,
                        "heuristicFactors": heuristic_result.factors.__dict__,
                        "lastHeuristicResult": {
                            "nextAnalysisHours": heuristic_result.next_analysis_hours,
                            "reasoning": heuristic_result.reasoning,
                            "confidence": heuristic_result.confidence,
                        },
                        "autoAnalysisEnabled": True,
                    },
                },
            )

            # Store heuristic decision for learning
            await self.store_heuristic_decision(
                shop_id, heuristic_result, analysis_result
            )

            return {
                "success": True,
                "next_scheduled_time": next_scheduled_time,
                "heuristic_result": heuristic_result,
            }

        except Exception as e:
            logger.error(
                "Error scheduling next analysis", shop_id=shop_id, error=str(e)
            )
            return {"success": False, "error": str(e)}


# Global instance
heuristic_service = AnalysisHeuristicService()
