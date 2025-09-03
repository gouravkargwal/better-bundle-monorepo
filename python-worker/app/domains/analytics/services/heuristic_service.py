"""
Heuristic service for intelligent analysis scheduling decisions
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from app.core.logging import get_logger
from app.shared.decorators import async_timing, monitor
from app.shared.helpers import now_utc
from app.core.redis_client import streams_manager
from app.shared.constants.redis import (
    HEURISTIC_DECISION_REQUESTED_STREAM,
    HEURISTIC_DECISION_MADE_STREAM,
    NEXT_ANALYSIS_SCHEDULED_STREAM,
)


class AnalysisTriggerType(Enum):
    """Types of analysis triggers"""
    SCHEDULED = "scheduled"
    MODEL_PERFORMANCE_DECLINE = "model_performance_decline"
    DATA_DRIFT_DETECTED = "data_drift_detected"
    BUSINESS_METRICS_CHANGE = "business_metrics_change"
    CUSTOMER_BEHAVIOR_SHIFT = "customer_behavior_shift"
    SEASONAL_PATTERN = "seasonal_pattern"
    MANUAL_REQUEST = "manual_request"


class AnalysisPriority(Enum):
    """Analysis priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnalysisDecision:
    """Analysis scheduling decision"""
    shop_id: str
    trigger_type: AnalysisTriggerType
    priority: AnalysisPriority
    recommended_analysis_types: List[str]
    scheduled_time: datetime
    reasoning: str
    confidence_score: float
    metadata: Dict[str, Any]
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = now_utc()


@dataclass
class HeuristicContext:
    """Context for heuristic decision making"""
    shop_id: str
    current_time: datetime
    last_analysis_time: Optional[datetime]
    model_performance_metrics: Dict[str, Any]
    business_metrics: Dict[str, Any]
    data_freshness: Dict[str, Any]
    seasonal_factors: Dict[str, Any]
    customer_behavior_metrics: Dict[str, Any]
    market_conditions: Dict[str, Any]


class HeuristicService:
    """Intelligent service for determining when and what analysis to run"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Decision rules and thresholds
        self.analysis_intervals = {
            "business_metrics": timedelta(hours=6),      # Every 6 hours
            "performance_analytics": timedelta(hours=12), # Every 12 hours
            "customer_analytics": timedelta(hours=8),    # Every 8 hours
            "product_analytics": timedelta(hours=4),     # Every 4 hours
            "revenue_analytics": timedelta(hours=6),     # Every 6 hours
            "ml_model_retraining": timedelta(days=7),   # Every week
        }
        
        # Performance thresholds
        self.performance_thresholds = {
            "accuracy_decline": 0.05,      # 5% accuracy decline
            "data_drift_threshold": 0.15,  # 15% data drift
            "business_metric_change": 0.10, # 10% business metric change
        }
        
        # Seasonal patterns
        self.seasonal_patterns = {
            "holiday_season": {
                "months": [11, 12],  # November-December
                "analysis_frequency_multiplier": 2.0,  # Double frequency
                "priority_boost": AnalysisPriority.HIGH
            },
            "back_to_school": {
                "months": [8, 9],    # August-September
                "analysis_frequency_multiplier": 1.5,
                "priority_boost": AnalysisPriority.MEDIUM
            },
            "summer_sales": {
                "months": [6, 7],    # June-July
                "analysis_frequency_multiplier": 1.3,
                "priority_boost": AnalysisPriority.MEDIUM
            }
        }
    
    async def evaluate_analysis_need(self, shop_id: str) -> AnalysisDecision:
        """Evaluate if and when analysis should be run for a shop"""
        try:
            self.logger.info(f"Evaluating analysis need for shop: {shop_id}")
            
            # Gather context for decision making
            context = await self._gather_heuristic_context(shop_id)
            
            # Apply heuristic rules
            decision = await self._apply_heuristic_rules(context)
            
            # Publish decision to Redis stream
            await self._publish_decision(decision)
            
            self.logger.info(
                f"Analysis decision made",
                shop_id=shop_id,
                trigger_type=decision.trigger_type.value,
                priority=decision.priority.value,
                scheduled_time=decision.scheduled_time.isoformat()
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"Failed to evaluate analysis need: {e}", shop_id=shop_id)
            raise
    
    async def _gather_heuristic_context(self, shop_id: str) -> HeuristicContext:
        """Gather all context needed for heuristic decision making"""
        try:
            # Get current time
            current_time = now_utc()
            
            # Get last analysis time (this would come from database/Redis)
            last_analysis_time = await self._get_last_analysis_time(shop_id)
            
            # Get model performance metrics
            model_performance = await self._get_model_performance_metrics(shop_id)
            
            # Get business metrics
            business_metrics = await self._get_business_metrics(shop_id)
            
            # Get data freshness
            data_freshness = await self._get_data_freshness(shop_id)
            
            # Get seasonal factors
            seasonal_factors = await self._get_seasonal_factors(current_time)
            
            # Get customer behavior metrics
            customer_behavior = await self._get_customer_behavior_metrics(shop_id)
            
            # Get market conditions
            market_conditions = await self._get_market_conditions(shop_id)
            
            return HeuristicContext(
                shop_id=shop_id,
                current_time=current_time,
                last_analysis_time=last_analysis_time,
                model_performance_metrics=model_performance,
                business_metrics=business_metrics,
                data_freshness=data_freshness,
                seasonal_factors=seasonal_factors,
                customer_behavior_metrics=customer_behavior,
                market_conditions=market_conditions
            )
            
        except Exception as e:
            self.logger.error(f"Failed to gather heuristic context: {e}", shop_id=shop_id)
            raise
    
    async def _apply_heuristic_rules(self, context: HeuristicContext) -> AnalysisDecision:
        """Apply heuristic rules to determine analysis decision"""
        try:
            # Initialize decision components
            trigger_type = AnalysisTriggerType.SCHEDULED
            priority = AnalysisPriority.MEDIUM
            recommended_analysis_types = []
            scheduled_time = context.current_time
            reasoning = []
            confidence_score = 0.5
            
            # Rule 1: Time-based scheduling
            time_based_decision = self._evaluate_time_based_analysis(context)
            if time_based_decision["should_run"]:
                trigger_type = AnalysisTriggerType.SCHEDULED
                recommended_analysis_types.extend(time_based_decision["analysis_types"])
                reasoning.append("Scheduled analysis interval reached")
                confidence_score += 0.2
            
            # Rule 2: Model performance decline
            performance_decision = self._evaluate_model_performance(context)
            if performance_decision["should_run"]:
                trigger_type = AnalysisTriggerType.MODEL_PERFORMANCE_DECLINE
                priority = AnalysisPriority.HIGH
                recommended_analysis_types.extend(performance_decision["analysis_types"])
                reasoning.append(f"Model performance declined: {performance_decision['reason']}")
                confidence_score += 0.3
            
            # Rule 3: Data drift detection
            drift_decision = self._evaluate_data_drift(context)
            if drift_decision["should_run"]:
                trigger_type = AnalysisTriggerType.DATA_DRIFT_DETECTED
                priority = AnalysisPriority.HIGH
                recommended_analysis_types.extend(drift_decision["analysis_types"])
                reasoning.append(f"Data drift detected: {drift_decision['reason']}")
                confidence_score += 0.25
            
            # Rule 4: Business metrics change
            business_decision = self._evaluate_business_metrics_change(context)
            if business_decision["should_run"]:
                trigger_type = AnalysisTriggerType.BUSINESS_METRICS_CHANGE
                priority = AnalysisPriority.MEDIUM
                recommended_analysis_types.extend(business_decision["analysis_types"])
                reasoning.append(f"Business metrics changed: {business_decision['reason']}")
                confidence_score += 0.2
            
            # Rule 5: Customer behavior shift
            customer_decision = self._evaluate_customer_behavior_shift(context)
            if customer_decision["should_run"]:
                trigger_type = AnalysisTriggerType.CUSTOMER_BEHAVIOR_SHIFT
                priority = AnalysisPriority.MEDIUM
                recommended_analysis_types.extend(customer_decision["analysis_types"])
                reasoning.append(f"Customer behavior shift: {customer_decision['reason']}")
                confidence_score += 0.15
            
            # Rule 6: Seasonal patterns
            seasonal_decision = self._evaluate_seasonal_patterns(context)
            if seasonal_decision["should_run"]:
                trigger_type = AnalysisTriggerType.SEASONAL_PATTERN
                priority = max(priority, seasonal_decision["priority"])
                recommended_analysis_types.extend(seasonal_decision["analysis_types"])
                reasoning.append(f"Seasonal pattern detected: {seasonal_decision['reason']}")
                confidence_score += 0.1
            
            # Determine final scheduled time
            scheduled_time = self._calculate_optimal_schedule_time(context, priority)
            
            # Remove duplicates and ensure we have analysis types
            recommended_analysis_types = list(set(recommended_analysis_types))
            if not recommended_analysis_types:
                recommended_analysis_types = ["business_metrics", "performance_analytics"]
            
            # Cap confidence score
            confidence_score = min(confidence_score, 1.0)
            
            # Combine reasoning
            final_reasoning = "; ".join(reasoning) if reasoning else "Default analysis schedule"
            
            return AnalysisDecision(
                shop_id=context.shop_id,
                trigger_type=trigger_type,
                priority=priority,
                recommended_analysis_types=recommended_analysis_types,
                scheduled_time=scheduled_time,
                reasoning=final_reasoning,
                confidence_score=confidence_score,
                metadata={
                    "context_gathered_at": context.current_time.isoformat(),
                    "rules_evaluated": len(reasoning),
                    "seasonal_factors": context.seasonal_factors,
                    "model_performance": context.model_performance_metrics
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to apply heuristic rules: {e}", shop_id=context.shop_id)
            raise
    
    def _evaluate_time_based_analysis(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on time intervals"""
        if not context.last_analysis_time:
            return {"should_run": True, "analysis_types": list(self.analysis_intervals.keys())}
        
        time_since_last = context.current_time - context.last_analysis_time
        should_run = False
        analysis_types = []
        
        for analysis_type, interval in self.analysis_intervals.items():
            if time_since_last >= interval:
                should_run = True
                analysis_types.append(analysis_type)
        
        return {"should_run": should_run, "analysis_types": analysis_types}
    
    def _evaluate_model_performance(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on model performance"""
        metrics = context.model_performance_metrics
        should_run = False
        analysis_types = []
        reason = ""
        
        # Check accuracy decline
        if "accuracy" in metrics and "previous_accuracy" in metrics:
            accuracy_decline = metrics["previous_accuracy"] - metrics["accuracy"]
            if accuracy_decline > self.performance_thresholds["accuracy_decline"]:
                should_run = True
                analysis_types.extend(["ml_model_retraining", "performance_analytics"])
                reason = f"Accuracy declined by {accuracy_decline:.2%}"
        
        # Check other performance metrics
        if "f1_score" in metrics and metrics["f1_score"] < 0.7:
            should_run = True
            analysis_types.append("ml_model_retraining")
            reason = f"Low F1 score: {metrics['f1_score']:.3f}"
        
        return {"should_run": should_run, "analysis_types": analysis_types, "reason": reason}
    
    def _evaluate_data_drift(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on data drift"""
        data_freshness = context.data_freshness
        should_run = False
        analysis_types = []
        reason = ""
        
        # Check data age
        for data_type, age_hours in data_freshness.items():
            if age_hours > 24:  # Data older than 24 hours
                should_run = True
                analysis_types.append("data_collection")
                reason = f"Data stale for {data_type}: {age_hours}h old"
                break
        
        return {"should_run": should_run, "analysis_types": analysis_types, "reason": reason}
    
    def _evaluate_business_metrics_change(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on business metrics change"""
        business_metrics = context.business_metrics
        should_run = False
        analysis_types = []
        reason = ""
        
        # Check revenue change
        if "revenue_change_pct" in business_metrics:
            change = abs(business_metrics["revenue_change_pct"])
            if change > self.performance_thresholds["business_metric_change"]:
                should_run = True
                analysis_types.extend(["revenue_analytics", "business_metrics"])
                reason = f"Revenue changed by {change:.1%}"
        
        # Check conversion rate change
        if "conversion_rate_change_pct" in business_metrics:
            change = abs(business_metrics["conversion_rate_change_pct"])
            if change > self.performance_thresholds["business_metric_change"]:
                should_run = True
                analysis_types.extend(["performance_analytics", "customer_analytics"])
                reason = f"Conversion rate changed by {change:.1%}"
        
        return {"should_run": should_run, "analysis_types": analysis_types, "reason": reason}
    
    def _evaluate_customer_behavior_shift(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on customer behavior changes"""
        customer_metrics = context.customer_behavior_metrics
        should_run = False
        analysis_types = []
        reason = ""
        
        # Check customer retention change
        if "retention_rate_change_pct" in customer_metrics:
            change = abs(customer_metrics["retention_rate_change_pct"])
            if change > self.performance_thresholds["business_metric_change"]:
                should_run = True
                analysis_types.extend(["customer_analytics", "performance_analytics"])
                reason = f"Customer retention changed by {change:.1%}"
        
        return {"should_run": should_run, "analysis_types": analysis_types, "reason": reason}
    
    def _evaluate_seasonal_patterns(self, context: HeuristicContext) -> Dict[str, Any]:
        """Evaluate if analysis should run based on seasonal patterns"""
        current_month = context.current_time.month
        should_run = False
        analysis_types = []
        reason = ""
        priority = AnalysisPriority.LOW
        
        for season_name, pattern in self.seasonal_patterns.items():
            if current_month in pattern["months"]:
                should_run = True
                analysis_types.extend(["business_metrics", "performance_analytics", "revenue_analytics"])
                reason = f"Seasonal pattern: {season_name}"
                priority = pattern["priority_boost"]
                break
        
        return {
            "should_run": should_run, 
            "analysis_types": analysis_types, 
            "reason": reason,
            "priority": priority
        }
    
    def _calculate_optimal_schedule_time(self, context: HeuristicContext, priority: AnalysisPriority) -> datetime:
        """Calculate optimal time to schedule the analysis"""
        base_time = context.current_time
        
        # Adjust based on priority
        if priority == AnalysisPriority.CRITICAL:
            # Run immediately
            return base_time
        elif priority == AnalysisPriority.HIGH:
            # Run within 1 hour
            return base_time + timedelta(minutes=30)
        elif priority == AnalysisPriority.MEDIUM:
            # Run within 2-4 hours
            return base_time + timedelta(hours=2)
        else:  # LOW priority
            # Run within 6-12 hours
            return base_time + timedelta(hours=6)
    
    async def _publish_decision(self, decision: AnalysisDecision):
        """Publish analysis decision to Redis streams"""
        try:
            # Publish to decision made stream
            await streams_manager.publish_event(
                HEURISTIC_DECISION_MADE_STREAM,
                {
                    "shop_id": decision.shop_id,
                    "decision": {
                        "trigger_type": decision.trigger_type.value,
                        "priority": decision.priority.value,
                        "recommended_analysis_types": decision.recommended_analysis_types,
                        "scheduled_time": decision.scheduled_time.isoformat(),
                        "reasoning": decision.reasoning,
                        "confidence_score": decision.confidence_score,
                        "metadata": decision.metadata
                    },
                    "timestamp": now_utc().isoformat()
                }
            )
            
            # Publish to next analysis scheduled stream
            await streams_manager.publish_event(
                NEXT_ANALYSIS_SCHEDULED_STREAM,
                {
                    "shop_id": decision.shop_id,
                    "analysis_types": decision.recommended_analysis_types,
                    "scheduled_time": decision.scheduled_time.isoformat(),
                    "priority": decision.priority.value,
                    "trigger_type": decision.trigger_type.value,
                    "timestamp": now_utc().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to publish decision: {e}", shop_id=decision.shop_id)
    
    # Mock methods for context gathering (in real implementation, these would fetch from services)
    async def _get_last_analysis_time(self, shop_id: str) -> Optional[datetime]:
        """Get last analysis time for a shop"""
        # Mock implementation - would fetch from database/Redis
        return now_utc() - timedelta(hours=8)
    
    async def _get_model_performance_metrics(self, shop_id: str) -> Dict[str, Any]:
        """Get ML model performance metrics"""
        # Mock implementation - would fetch from ML service
        return {
            "accuracy": 0.85,
            "previous_accuracy": 0.89,
            "f1_score": 0.82,
            "precision": 0.87,
            "recall": 0.78
        }
    
    async def _get_business_metrics(self, shop_id: str) -> Dict[str, Any]:
        """Get business metrics"""
        # Mock implementation - would fetch from analytics service
        return {
            "revenue_change_pct": 0.05,
            "conversion_rate_change_pct": -0.02,
            "average_order_value": 125.50,
            "total_orders": 150
        }
    
    async def _get_data_freshness(self, shop_id: str) -> Dict[str, Any]:
        """Get data freshness metrics"""
        # Mock implementation - would fetch from data service
        return {
            "products": 2,      # 2 hours old
            "orders": 1,        # 1 hour old
            "customers": 3,     # 3 hours old
            "collections": 4    # 4 hours old
        }
    
    async def _get_seasonal_factors(self, current_time: datetime) -> Dict[str, Any]:
        """Get seasonal factors"""
        current_month = current_time.month
        seasonal_info = {}
        
        for season_name, pattern in self.seasonal_patterns.items():
            if current_month in pattern["months"]:
                seasonal_info[season_name] = {
                    "active": True,
                    "multiplier": pattern["analysis_frequency_multiplier"],
                    "priority_boost": pattern["priority_boost"].value
                }
            else:
                seasonal_info[season_name] = {"active": False}
        
        return seasonal_info
    
    async def _get_customer_behavior_metrics(self, shop_id: str) -> Dict[str, Any]:
        """Get customer behavior metrics"""
        # Mock implementation - would fetch from customer analytics service
        return {
            "retention_rate_change_pct": 0.01,
            "customer_lifetime_value": 450.00,
            "repeat_purchase_rate": 0.35,
            "churn_rate": 0.08
        }
    
    async def _get_market_conditions(self, shop_id: str) -> Dict[str, Any]:
        """Get market conditions"""
        # Mock implementation - would fetch from external market data
        return {
            "market_volatility": "low",
            "competition_level": "medium",
            "economic_indicator": "stable"
        }
