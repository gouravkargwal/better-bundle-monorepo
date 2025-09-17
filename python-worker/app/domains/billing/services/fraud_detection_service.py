"""
Fraud Detection Service

This service monitors for suspicious patterns in billing and attribution data
to prevent fraud and ensure billing accuracy.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from prisma import Prisma

logger = logging.getLogger(__name__)


class FraudRiskLevel(Enum):
    """Fraud risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudType(Enum):
    """Types of fraud detected"""
    EXCESSIVE_INTERACTIONS = "excessive_interactions"
    RAPID_FIRE_CLICKS = "rapid_fire_clicks"
    UNUSUAL_CONVERSION_RATE = "unusual_conversion_rate"
    SUSPICIOUS_REVENUE_PATTERN = "suspicious_revenue_pattern"
    BOT_TRAFFIC = "bot_traffic"
    CLICK_FARM = "click_farm"
    REVENUE_MANIPULATION = "revenue_manipulation"


@dataclass
class FraudDetectionResult:
    """Result of fraud detection analysis"""
    shop_id: str
    risk_level: FraudRiskLevel
    fraud_types: List[FraudType]
    confidence_score: float  # 0.0 to 1.0
    suspicious_metrics: Dict[str, Any]
    recommendations: List[str]
    detected_at: datetime
    period_start: datetime
    period_end: datetime


@dataclass
class FraudThresholds:
    """Configurable fraud detection thresholds"""
    # Interaction thresholds
    max_interactions_per_hour: int = 1000
    max_interactions_per_day: int = 10000
    max_rapid_clicks_per_minute: int = 50
    
    # Conversion rate thresholds
    min_conversion_rate: float = 0.001  # 0.1%
    max_conversion_rate: float = 0.5    # 50%
    
    # Revenue thresholds
    max_revenue_per_hour: Decimal = Decimal("10000")
    max_revenue_per_day: Decimal = Decimal("100000")
    
    # Pattern detection
    max_same_ip_interactions: int = 100
    max_same_user_agent_interactions: int = 200
    
    # Time-based patterns
    min_session_duration: int = 1  # seconds
    max_sessions_per_ip_per_hour: int = 50


class FraudDetectionService:
    """
    Service for detecting fraudulent patterns in billing and attribution data.
    """
    
    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.thresholds = FraudThresholds()
    
    async def analyze_shop_fraud_risk(
        self,
        shop_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> FraudDetectionResult:
        """
        Analyze fraud risk for a shop over a given period.
        
        Args:
            shop_id: Shop ID
            period_start: Analysis start date (defaults to last 7 days)
            period_end: Analysis end date (defaults to now)
            
        Returns:
            Fraud detection result
        """
        try:
            # Set default period if not provided
            if not period_end:
                period_end = datetime.utcnow()
            if not period_start:
                period_start = period_end - timedelta(days=7)
            
            logger.info(f"Analyzing fraud risk for shop {shop_id} from {period_start} to {period_end}")
            
            # Get interaction data
            interactions = await self._get_interaction_data(shop_id, period_start, period_end)
            
            # Get purchase data
            purchases = await self._get_purchase_data(shop_id, period_start, period_end)
            
            # Analyze patterns
            fraud_analysis = await self._analyze_fraud_patterns(interactions, purchases)
            
            # Calculate risk level and confidence
            risk_level, confidence = self._calculate_risk_level(fraud_analysis)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(fraud_analysis, risk_level)
            
            result = FraudDetectionResult(
                shop_id=shop_id,
                risk_level=risk_level,
                fraud_types=fraud_analysis["detected_fraud_types"],
                confidence_score=confidence,
                suspicious_metrics=fraud_analysis["suspicious_metrics"],
                recommendations=recommendations,
                detected_at=datetime.utcnow(),
                period_start=period_start,
                period_end=period_end
            )
            
            # Store fraud detection result
            await self._store_fraud_detection_result(result)
            
            logger.info(f"Fraud analysis completed for shop {shop_id}: {risk_level.value} risk, confidence: {confidence:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing fraud risk for shop {shop_id}: {e}")
            raise
    
    async def _get_interaction_data(
        self,
        shop_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get interaction data for fraud analysis."""
        try:
            # Get user interactions
            interactions = await self.prisma.userInteraction.findMany(
                where={
                    "shopId": shop_id,
                    "timestamp": {
                        "gte": period_start,
                        "lte": period_end
                    }
                },
                include={
                    "session": True
                }
            )
            
            # Convert to list of dictionaries
            interaction_data = []
            for interaction in interactions:
                interaction_data.append({
                    "id": interaction.id,
                    "session_id": interaction.sessionId,
                    "customer_id": interaction.customerId,
                    "extension": interaction.extension,
                    "action": interaction.action,
                    "timestamp": interaction.timestamp,
                    "metadata": interaction.metadata,
                    "session": {
                        "id": interaction.session.id if interaction.session else None,
                        "ip_address": interaction.session.ipAddress if interaction.session else None,
                        "user_agent": interaction.session.userAgent if interaction.session else None,
                        "duration": interaction.session.duration if interaction.session else None
                    } if interaction.session else None
                })
            
            return interaction_data
            
        except Exception as e:
            logger.error(f"Error getting interaction data for shop {shop_id}: {e}")
            return []
    
    async def _get_purchase_data(
        self,
        shop_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get purchase data for fraud analysis."""
        try:
            # Get purchase attributions
            purchases = await self.prisma.purchaseAttribution.findMany(
                where={
                    "shopId": shop_id,
                    "purchaseDate": {
                        "gte": period_start,
                        "lte": period_end
                    }
                }
            )
            
            # Convert to list of dictionaries
            purchase_data = []
            for purchase in purchases:
                purchase_data.append({
                    "id": purchase.id,
                    "order_id": purchase.orderId,
                    "customer_id": purchase.customerId,
                    "total_amount": purchase.totalAmount,
                    "attributed_revenue": purchase.attributedRevenue,
                    "purchase_date": purchase.purchaseDate,
                    "attribution_breakdown": purchase.attributionBreakdown
                })
            
            return purchase_data
            
        except Exception as e:
            logger.error(f"Error getting purchase data for shop {shop_id}: {e}")
            return []
    
    async def _analyze_fraud_patterns(
        self,
        interactions: List[Dict[str, Any]],
        purchases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze patterns to detect fraud."""
        fraud_types = []
        suspicious_metrics = {}
        
        # 1. Excessive interactions analysis
        excessive_interactions = self._detect_excessive_interactions(interactions)
        if excessive_interactions["detected"]:
            fraud_types.append(FraudType.EXCESSIVE_INTERACTIONS)
            suspicious_metrics["excessive_interactions"] = excessive_interactions
        
        # 2. Rapid fire clicks analysis
        rapid_clicks = self._detect_rapid_fire_clicks(interactions)
        if rapid_clicks["detected"]:
            fraud_types.append(FraudType.RAPID_FIRE_CLICKS)
            suspicious_metrics["rapid_fire_clicks"] = rapid_clicks
        
        # 3. Unusual conversion rate analysis
        conversion_anomaly = self._detect_conversion_anomaly(interactions, purchases)
        if conversion_anomaly["detected"]:
            fraud_types.append(FraudType.UNUSUAL_CONVERSION_RATE)
            suspicious_metrics["conversion_anomaly"] = conversion_anomaly
        
        # 4. Suspicious revenue pattern analysis
        revenue_anomaly = self._detect_revenue_anomaly(purchases)
        if revenue_anomaly["detected"]:
            fraud_types.append(FraudType.SUSPICIOUS_REVENUE_PATTERN)
            suspicious_metrics["revenue_anomaly"] = revenue_anomaly
        
        # 5. Bot traffic analysis
        bot_traffic = self._detect_bot_traffic(interactions)
        if bot_traffic["detected"]:
            fraud_types.append(FraudType.BOT_TRAFFIC)
            suspicious_metrics["bot_traffic"] = bot_traffic
        
        # 6. Click farm analysis
        click_farm = self._detect_click_farm(interactions)
        if click_farm["detected"]:
            fraud_types.append(FraudType.CLICK_FARM)
            suspicious_metrics["click_farm"] = click_farm
        
        return {
            "detected_fraud_types": fraud_types,
            "suspicious_metrics": suspicious_metrics,
            "total_interactions": len(interactions),
            "total_purchases": len(purchases)
        }
    
    def _detect_excessive_interactions(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect excessive interaction patterns."""
        if not interactions:
            return {"detected": False}
        
        # Group by hour
        hourly_counts = {}
        daily_counts = {}
        
        for interaction in interactions:
            timestamp = interaction["timestamp"]
            hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
            day_key = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
        
        # Check thresholds
        max_hourly = max(hourly_counts.values()) if hourly_counts else 0
        max_daily = max(daily_counts.values()) if daily_counts else 0
        
        detected = (
            max_hourly > self.thresholds.max_interactions_per_hour or
            max_daily > self.thresholds.max_interactions_per_day
        )
        
        return {
            "detected": detected,
            "max_hourly_interactions": max_hourly,
            "max_daily_interactions": max_daily,
            "threshold_hourly": self.thresholds.max_interactions_per_hour,
            "threshold_daily": self.thresholds.max_interactions_per_day
        }
    
    def _detect_rapid_fire_clicks(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect rapid fire click patterns."""
        if not interactions:
            return {"detected": False}
        
        # Group by minute and count clicks
        minute_counts = {}
        for interaction in interactions:
            if interaction["action"] in ["click", "view", "recommendation_click"]:
                minute_key = interaction["timestamp"].replace(second=0, microsecond=0)
                minute_counts[minute_key] = minute_counts.get(minute_key, 0) + 1
        
        max_clicks_per_minute = max(minute_counts.values()) if minute_counts else 0
        detected = max_clicks_per_minute > self.thresholds.max_rapid_clicks_per_minute
        
        return {
            "detected": detected,
            "max_clicks_per_minute": max_clicks_per_minute,
            "threshold": self.thresholds.max_rapid_clicks_per_minute
        }
    
    def _detect_conversion_anomaly(
        self,
        interactions: List[Dict[str, Any]],
        purchases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect unusual conversion rate patterns."""
        if not interactions:
            return {"detected": False}
        
        # Calculate conversion rate
        total_interactions = len(interactions)
        total_purchases = len(purchases)
        conversion_rate = total_purchases / total_interactions if total_interactions > 0 else 0
        
        # Check if conversion rate is suspicious
        detected = (
            conversion_rate < self.thresholds.min_conversion_rate or
            conversion_rate > self.thresholds.max_conversion_rate
        )
        
        return {
            "detected": detected,
            "conversion_rate": conversion_rate,
            "total_interactions": total_interactions,
            "total_purchases": total_purchases,
            "min_threshold": self.thresholds.min_conversion_rate,
            "max_threshold": self.thresholds.max_conversion_rate
        }
    
    def _detect_revenue_anomaly(self, purchases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect suspicious revenue patterns."""
        if not purchases:
            return {"detected": False}
        
        # Group by hour and day
        hourly_revenue = {}
        daily_revenue = {}
        
        for purchase in purchases:
            timestamp = purchase["purchase_date"]
            amount = Decimal(str(purchase["attributed_revenue"]))
            
            hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
            day_key = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            
            hourly_revenue[hour_key] = hourly_revenue.get(hour_key, Decimal("0")) + amount
            daily_revenue[day_key] = daily_revenue.get(day_key, Decimal("0")) + amount
        
        max_hourly_revenue = max(hourly_revenue.values()) if hourly_revenue else Decimal("0")
        max_daily_revenue = max(daily_revenue.values()) if daily_revenue else Decimal("0")
        
        detected = (
            max_hourly_revenue > self.thresholds.max_revenue_per_hour or
            max_daily_revenue > self.thresholds.max_revenue_per_day
        )
        
        return {
            "detected": detected,
            "max_hourly_revenue": float(max_hourly_revenue),
            "max_daily_revenue": float(max_daily_revenue),
            "threshold_hourly": float(self.thresholds.max_revenue_per_hour),
            "threshold_daily": float(self.thresholds.max_revenue_per_day)
        }
    
    def _detect_bot_traffic(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect bot traffic patterns."""
        if not interactions:
            return {"detected": False}
        
        # Analyze IP addresses and user agents
        ip_counts = {}
        user_agent_counts = {}
        short_sessions = 0
        
        for interaction in interactions:
            session = interaction.get("session")
            if not session:
                continue
            
            # Count IP addresses
            ip = session.get("ip_address")
            if ip:
                ip_counts[ip] = ip_counts.get(ip, 0) + 1
            
            # Count user agents
            user_agent = session.get("user_agent")
            if user_agent:
                user_agent_counts[user_agent] = user_agent_counts.get(user_agent, 0) + 1
            
            # Check for very short sessions (potential bots)
            duration = session.get("duration")
            if duration and duration < self.thresholds.min_session_duration:
                short_sessions += 1
        
        # Check for suspicious patterns
        max_ip_interactions = max(ip_counts.values()) if ip_counts else 0
        max_user_agent_interactions = max(user_agent_counts.values()) if user_agent_counts else 0
        short_session_ratio = short_sessions / len(interactions) if interactions else 0
        
        detected = (
            max_ip_interactions > self.thresholds.max_same_ip_interactions or
            max_user_agent_interactions > self.thresholds.max_same_user_agent_interactions or
            short_session_ratio > 0.8  # 80% of sessions are very short
        )
        
        return {
            "detected": detected,
            "max_ip_interactions": max_ip_interactions,
            "max_user_agent_interactions": max_user_agent_interactions,
            "short_sessions": short_sessions,
            "short_session_ratio": short_session_ratio,
            "threshold_ip": self.thresholds.max_same_ip_interactions,
            "threshold_user_agent": self.thresholds.max_same_user_agent_interactions
        }
    
    def _detect_click_farm(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect click farm patterns."""
        if not interactions:
            return {"detected": False}
        
        # Group by IP and count sessions per hour
        ip_hourly_sessions = {}
        
        for interaction in interactions:
            session = interaction.get("session")
            if not session or not session.get("ip_address"):
                continue
            
            ip = session["ip_address"]
            hour_key = interaction["timestamp"].replace(minute=0, second=0, microsecond=0)
            
            if ip not in ip_hourly_sessions:
                ip_hourly_sessions[ip] = {}
            
            if hour_key not in ip_hourly_sessions[ip]:
                ip_hourly_sessions[ip][hour_key] = set()
            
            ip_hourly_sessions[ip][hour_key].add(interaction["session_id"])
        
        # Check for IPs with too many sessions per hour
        suspicious_ips = []
        for ip, hourly_sessions in ip_hourly_sessions.items():
            for hour, sessions in hourly_sessions.items():
                if len(sessions) > self.thresholds.max_sessions_per_ip_per_hour:
                    suspicious_ips.append({
                        "ip": ip,
                        "hour": hour,
                        "session_count": len(sessions)
                    })
        
        detected = len(suspicious_ips) > 0
        
        return {
            "detected": detected,
            "suspicious_ips": suspicious_ips,
            "threshold": self.thresholds.max_sessions_per_ip_per_hour
        }
    
    def _calculate_risk_level(self, fraud_analysis: Dict[str, Any]) -> Tuple[FraudRiskLevel, float]:
        """Calculate overall risk level and confidence score."""
        fraud_types = fraud_analysis["detected_fraud_types"]
        suspicious_metrics = fraud_analysis["suspicious_metrics"]
        
        if not fraud_types:
            return FraudRiskLevel.LOW, 0.1
        
        # Calculate confidence based on number and severity of fraud types
        confidence = min(0.9, len(fraud_types) * 0.2 + 0.3)
        
        # Determine risk level based on fraud types and severity
        if len(fraud_types) >= 4 or any(metric.get("detected", False) for metric in suspicious_metrics.values() if isinstance(metric, dict) and metric.get("detected")):
            risk_level = FraudRiskLevel.CRITICAL
        elif len(fraud_types) >= 3:
            risk_level = FraudRiskLevel.HIGH
        elif len(fraud_types) >= 2:
            risk_level = FraudRiskLevel.MEDIUM
        else:
            risk_level = FraudRiskLevel.LOW
        
        return risk_level, confidence
    
    def _generate_recommendations(
        self,
        fraud_analysis: Dict[str, Any],
        risk_level: FraudRiskLevel
    ) -> List[str]:
        """Generate recommendations based on fraud analysis."""
        recommendations = []
        fraud_types = fraud_analysis["detected_fraud_types"]
        
        if FraudType.EXCESSIVE_INTERACTIONS in fraud_types:
            recommendations.append("Consider implementing rate limiting for interactions")
        
        if FraudType.RAPID_FIRE_CLICKS in fraud_types:
            recommendations.append("Add click throttling to prevent rapid-fire clicking")
        
        if FraudType.UNUSUAL_CONVERSION_RATE in fraud_types:
            recommendations.append("Review conversion tracking and attribution logic")
        
        if FraudType.SUSPICIOUS_REVENUE_PATTERN in fraud_types:
            recommendations.append("Investigate revenue patterns and validate purchases")
        
        if FraudType.BOT_TRAFFIC in fraud_types:
            recommendations.append("Implement bot detection and CAPTCHA challenges")
        
        if FraudType.CLICK_FARM in fraud_types:
            recommendations.append("Block suspicious IP addresses and implement IP-based restrictions")
        
        # General recommendations based on risk level
        if risk_level == FraudRiskLevel.CRITICAL:
            recommendations.append("Immediately suspend billing and investigate further")
            recommendations.append("Contact merchant to verify legitimate traffic")
        elif risk_level == FraudRiskLevel.HIGH:
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Consider temporary billing suspension")
        elif risk_level == FraudRiskLevel.MEDIUM:
            recommendations.append("Monitor closely for the next billing period")
            recommendations.append("Review attribution rules and thresholds")
        
        return recommendations
    
    async def _store_fraud_detection_result(self, result: FraudDetectionResult) -> None:
        """Store fraud detection result in database."""
        try:
            # Store in billing events
            await self.prisma.billingEvent.create({
                "data": {
                    "shop_id": result.shop_id,
                    "risk_level": result.risk_level.value,
                    "fraud_types": [ft.value for ft in result.fraud_types],
                    "confidence_score": result.confidence_score,
                    "suspicious_metrics": result.suspicious_metrics,
                    "recommendations": result.recommendations,
                    "period_start": result.period_start.isoformat(),
                    "period_end": result.period_end.isoformat()
                },
                "metadata": {
                    "detection_type": "fraud_analysis",
                    "detected_at": result.detected_at.isoformat()
                },
                "shopId": result.shop_id,
                "type": "fraud_detected",
                "occurredAt": result.detected_at
            })
            
        except Exception as e:
            logger.error(f"Error storing fraud detection result: {e}")
    
    async def get_fraud_detection_history(
        self,
        shop_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get fraud detection history for a shop."""
        try:
            events = await self.prisma.billingEvent.findMany(
                where={
                    "shopId": shop_id,
                    "type": "fraud_detected"
                },
                orderBy={
                    "occurredAt": "desc"
                },
                take=limit
            )
            
            return [
                {
                    "id": event.id,
                    "risk_level": event.data.get("risk_level"),
                    "fraud_types": event.data.get("fraud_types", []),
                    "confidence_score": event.data.get("confidence_score"),
                    "recommendations": event.data.get("recommendations", []),
                    "detected_at": event.occurredAt.isoformat()
                }
                for event in events
            ]
            
        except Exception as e:
            logger.error(f"Error getting fraud detection history for shop {shop_id}: {e}")
            return []
    
    async def update_fraud_thresholds(self, new_thresholds: Dict[str, Any]) -> None:
        """Update fraud detection thresholds."""
        try:
            for key, value in new_thresholds.items():
                if hasattr(self.thresholds, key):
                    setattr(self.thresholds, key, value)
            
            logger.info("Fraud detection thresholds updated")
            
        except Exception as e:
            logger.error(f"Error updating fraud thresholds: {e}")
            raise
