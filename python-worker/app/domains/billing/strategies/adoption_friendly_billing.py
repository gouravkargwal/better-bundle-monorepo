"""
Adoption-Friendly Billing Strategy

This module implements billing strategies that minimize adoption friction
while ensuring sustainable revenue for the app.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class BillingTier(Enum):
    """Billing tiers for different merchant segments"""

    STARTER = "starter"  # New merchants, low volume
    GROWTH = "growth"  # Growing merchants, medium volume
    ENTERPRISE = "enterprise"  # Large merchants, high volume


class AdoptionFriendlyBillingStrategy:
    """
    Billing strategy focused on minimizing adoption friction
    while ensuring sustainable revenue.
    """

    def __init__(self):
        self.billing_tiers = {
            BillingTier.STARTER: {
                "name": "Starter Plan",
                "capped_amount": 50.0,  # $50/month max
                "commission_rate": 0.03,  # 3%
                "trial_threshold": 100.0,  # $100 revenue threshold
                "trial_duration_days": 30,  # 30-day trial
                "min_monthly_charge": 0.0,  # No minimum
                "description": "Perfect for new stores - 3% of attributed revenue, max $50/month",
            },
            BillingTier.GROWTH: {
                "name": "Growth Plan",
                "capped_amount": 200.0,  # $200/month max
                "commission_rate": 0.03,  # 3%
                "trial_threshold": 500.0,  # $500 revenue threshold
                "trial_duration_days": 14,  # 14-day trial
                "min_monthly_charge": 0.0,  # No minimum
                "description": "For growing stores - 3% of attributed revenue, max $200/month",
            },
            BillingTier.ENTERPRISE: {
                "name": "Enterprise Plan",
                "capped_amount": 1000.0,  # $1000/month max
                "commission_rate": 0.025,  # 2.5% (better rate)
                "trial_threshold": 2000.0,  # $2000 revenue threshold
                "trial_duration_days": 7,  # 7-day trial
                "min_monthly_charge": 0.0,  # No minimum
                "description": "For high-volume stores - 2.5% of attributed revenue, max $1000/month",
            },
        }

    def get_optimal_tier(self, shop_data: Dict[str, Any]) -> BillingTier:
        """
        Determine optimal billing tier based on shop characteristics.

        Args:
            shop_data: Shop information including plan, revenue, etc.

        Returns:
            Optimal billing tier
        """
        try:
            # Get shop plan type
            shop_plan = shop_data.get("plan", {}).get("displayName", "Basic")

            # Get estimated monthly revenue (if available)
            estimated_revenue = shop_data.get("estimated_monthly_revenue", 0)

            # Determine tier based on shop characteristics
            if shop_plan in ["Plus", "Advanced"] or estimated_revenue > 50000:
                return BillingTier.ENTERPRISE
            elif shop_plan in ["Shopify", "Professional"] or estimated_revenue > 10000:
                return BillingTier.GROWTH
            else:
                return BillingTier.STARTER

        except Exception as e:
            logger.error(f"Error determining billing tier: {e}")
            return BillingTier.STARTER

    def create_adoption_friendly_subscription(
        self, shop_data: Dict[str, Any], currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Create a subscription with minimal adoption friction.

        Args:
            shop_data: Shop information
            currency: Store currency

        Returns:
            Subscription configuration
        """
        try:
            # Get optimal tier
            tier = self.get_optimal_tier(shop_data)
            tier_config = self.billing_tiers[tier]

            # Create subscription configuration
            subscription_config = {
                "name": f"Better Bundle - {tier_config['name']}",
                "return_url": f"{process.env.SHOPIFY_APP_URL}/billing/return",
                "line_items": [
                    {
                        "plan": {
                            "appUsagePricingDetails": {
                                "terms": tier_config["description"],
                                "cappedAmount": {
                                    "amount": tier_config["capped_amount"],
                                    "currencyCode": currency,
                                },
                            }
                        }
                    }
                ],
            }

            # Add trial information
            subscription_config["trial_info"] = {
                "tier": tier.value,
                "trial_threshold": tier_config["trial_threshold"],
                "trial_duration_days": tier_config["trial_duration_days"],
                "commission_rate": tier_config["commission_rate"],
                "capped_amount": tier_config["capped_amount"],
                "min_monthly_charge": tier_config["min_monthly_charge"],
            }

            logger.info(f"Created adoption-friendly subscription for tier {tier.value}")
            return subscription_config

        except Exception as e:
            logger.error(f"Error creating adoption-friendly subscription: {e}")
            return {}

    def get_payment_failure_strategy(self, failure_type: str) -> Dict[str, Any]:
        """
        Get strategy for handling payment failures.

        Args:
            failure_type: Type of payment failure

        Returns:
            Handling strategy
        """
        strategies = {
            "insufficient_funds": {
                "action": "grace_period",
                "grace_period_days": 7,
                "notifications": ["email", "in_app"],
                "service_impact": "limited_functionality",
                "retry_schedule": [1, 3, 7, 14],  # days
            },
            "declined_card": {
                "action": "immediate_notification",
                "grace_period_days": 3,
                "notifications": ["email", "in_app", "sms"],
                "service_impact": "limited_functionality",
                "retry_schedule": [1, 2, 3],
            },
            "expired_card": {
                "action": "update_payment_method",
                "grace_period_days": 5,
                "notifications": ["email", "in_app"],
                "service_impact": "limited_functionality",
                "retry_schedule": [1, 3, 5],
            },
            "capped_amount_reached": {
                "action": "upgrade_prompt",
                "grace_period_days": 0,
                "notifications": ["in_app", "email"],
                "service_impact": "usage_limited",
                "retry_schedule": [],
            },
        }

        return strategies.get(failure_type, strategies["insufficient_funds"])

    def create_payment_failure_flow(
        self, shop_id: str, failure_type: str
    ) -> Dict[str, Any]:
        """
        Create a payment failure handling flow.

        Args:
            shop_id: Shop ID
            failure_type: Type of payment failure

        Returns:
            Failure handling flow
        """
        try:
            strategy = self.get_payment_failure_strategy(failure_type)

            flow = {
                "shop_id": shop_id,
                "failure_type": failure_type,
                "strategy": strategy,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active",
                "next_action": self._get_next_action(strategy),
                "escalation_timeline": self._create_escalation_timeline(strategy),
            }

            logger.info(
                f"Created payment failure flow for shop {shop_id}: {failure_type}"
            )
            return flow

        except Exception as e:
            logger.error(f"Error creating payment failure flow: {e}")
            return {}

    def _get_next_action(self, strategy: Dict[str, Any]) -> str:
        """Get the next action based on strategy"""
        if strategy["action"] == "grace_period":
            return "Send notification and wait for payment"
        elif strategy["action"] == "immediate_notification":
            return "Send urgent notification to update payment method"
        elif strategy["action"] == "update_payment_method":
            return "Prompt user to update payment method"
        elif strategy["action"] == "upgrade_prompt":
            return "Offer plan upgrade to increase cap"
        else:
            return "Send standard notification"

    def _create_escalation_timeline(
        self, strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create escalation timeline for payment failures"""
        timeline = []

        for i, retry_day in enumerate(strategy["retry_schedule"]):
            timeline.append(
                {
                    "day": retry_day,
                    "action": f"Retry payment attempt {i + 1}",
                    "notification": "Send payment reminder",
                    "service_impact": strategy["service_impact"],
                }
            )

        # Final escalation
        timeline.append(
            {
                "day": strategy["grace_period_days"],
                "action": "Final escalation",
                "notification": "Send final notice",
                "service_impact": "service_suspended",
            }
        )

        return timeline


class PaymentFailureHandler:
    """Handles payment failures and service degradation"""

    def __init__(self, prisma, notification_service):
        self.prisma = prisma
        self.notification_service = notification_service
        self.strategy = AdoptionFriendlyBillingStrategy()

    async def handle_payment_failure(
        self, shop_id: str, failure_type: str, failure_details: Dict[str, Any]
    ) -> bool:
        """
        Handle payment failure for a shop.

        Args:
            shop_id: Shop ID
            failure_type: Type of payment failure
            failure_details: Additional failure details

        Returns:
            True if handled successfully
        """
        try:
            # Create failure flow
            flow = self.strategy.create_payment_failure_flow(shop_id, failure_type)

            # Update shop status
            await self._update_shop_payment_status(shop_id, failure_type)

            # Send notifications
            await self._send_failure_notifications(shop_id, flow)

            # Apply service limitations
            await self._apply_service_limitations(shop_id, flow)

            # Schedule retry attempts
            await self._schedule_retry_attempts(shop_id, flow)

            logger.info(f"Handled payment failure for shop {shop_id}: {failure_type}")
            return True

        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")
            return False

    async def _update_shop_payment_status(self, shop_id: str, failure_type: str):
        """Update shop payment status"""
        await self.prisma.shop.update_many(
            where={"id": shop_id},
            data={
                "paymentStatus": "failed",
                "paymentFailureType": failure_type,
                "paymentFailureAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            },
        )

    async def _send_failure_notifications(self, shop_id: str, flow: Dict[str, Any]):
        """Send failure notifications"""
        notifications = flow["strategy"]["notifications"]

        for notification_type in notifications:
            await self.notification_service.send_payment_failure_notification(
                shop_id=shop_id,
                notification_type=notification_type,
                failure_type=flow["failure_type"],
                next_action=flow["next_action"],
            )

    async def _apply_service_limitations(self, shop_id: str, flow: Dict[str, Any]):
        """Apply service limitations based on failure type"""
        service_impact = flow["strategy"]["service_impact"]

        if service_impact == "limited_functionality":
            # Limit some features but keep core functionality
            await self._limit_advanced_features(shop_id)
        elif service_impact == "usage_limited":
            # Limit usage to prevent exceeding cap
            await self._limit_usage_tracking(shop_id)
        elif service_impact == "service_suspended":
            # Suspend service completely
            await self._suspend_service(shop_id)

    async def _schedule_retry_attempts(self, shop_id: str, flow: Dict[str, Any]):
        """Schedule retry attempts"""
        retry_schedule = flow["strategy"]["retry_schedule"]

        for retry_day in retry_schedule:
            retry_date = datetime.utcnow() + timedelta(days=retry_day)

            # Schedule retry (this would integrate with your job queue)
            await self._schedule_retry_job(shop_id, retry_date, retry_day)

    async def _limit_advanced_features(self, shop_id: str):
        """Limit advanced features but keep core functionality"""
        # Implementation would depend on your app's features
        pass

    async def _limit_usage_tracking(self, shop_id: str):
        """Limit usage tracking to prevent exceeding cap"""
        # Implementation would depend on your usage tracking system
        pass

    async def _suspend_service(self, shop_id: str):
        """Suspend service completely"""
        await self.prisma.shop.update_many(
            where={"id": shop_id},
            data={
                "isActive": False,
                "suspendedAt": datetime.utcnow(),
                "suspensionReason": "payment_failure",
            },
        )
