"""
Payment Failure Service

This service handles payment failures, service degradation, and recovery
for usage-based billing subscriptions.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

from prisma import Prisma

logger = logging.getLogger(__name__)


class PaymentFailureType(Enum):
    """Types of payment failures"""

    INSUFFICIENT_FUNDS = "insufficient_funds"
    DECLINED_CARD = "declined_card"
    EXPIRED_CARD = "expired_card"
    CAPPED_AMOUNT_REACHED = "capped_amount_reached"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    PAYMENT_METHOD_INVALID = "payment_method_invalid"


class ServiceImpact(Enum):
    """Service impact levels"""

    NONE = "none"  # No impact
    LIMITED_FUNCTIONALITY = "limited"  # Some features disabled
    USAGE_LIMITED = "usage_limited"  # Usage tracking limited
    SERVICE_SUSPENDED = "suspended"  # Service completely suspended


class PaymentFailureService:
    """Service for handling payment failures and service degradation"""

    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.failure_strategies = {
            PaymentFailureType.INSUFFICIENT_FUNDS: {
                "grace_period_days": 7,
                "retry_schedule": [1, 3, 7, 14],
                "service_impact": ServiceImpact.LIMITED_FUNCTIONALITY,
                "notifications": ["email", "in_app"],
                "escalation_action": "service_suspension",
            },
            PaymentFailureType.DECLINED_CARD: {
                "grace_period_days": 3,
                "retry_schedule": [1, 2, 3],
                "service_impact": ServiceImpact.LIMITED_FUNCTIONALITY,
                "notifications": ["email", "in_app", "sms"],
                "escalation_action": "service_suspension",
            },
            PaymentFailureType.EXPIRED_CARD: {
                "grace_period_days": 5,
                "retry_schedule": [1, 3, 5],
                "service_impact": ServiceImpact.LIMITED_FUNCTIONALITY,
                "notifications": ["email", "in_app"],
                "escalation_action": "service_suspension",
            },
            PaymentFailureType.CAPPED_AMOUNT_REACHED: {
                "grace_period_days": 0,
                "retry_schedule": [],
                "service_impact": ServiceImpact.USAGE_LIMITED,
                "notifications": ["in_app", "email"],
                "escalation_action": "upgrade_prompt",
            },
            PaymentFailureType.SUBSCRIPTION_CANCELLED: {
                "grace_period_days": 0,
                "retry_schedule": [],
                "service_impact": ServiceImpact.SERVICE_SUSPENDED,
                "notifications": ["email", "in_app"],
                "escalation_action": "renewal_prompt",
            },
        }

    async def handle_payment_failure(
        self,
        shop_id: str,
        failure_type: PaymentFailureType,
        failure_details: Dict[str, Any],
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
            logger.info(
                f"Handling payment failure for shop {shop_id}: {failure_type.value}"
            )

            # Get failure strategy
            strategy = self.failure_strategies.get(failure_type)
            if not strategy:
                logger.error(f"No strategy found for failure type: {failure_type}")
                return False

            # Create failure record
            failure_record = await self._create_failure_record(
                shop_id, failure_type, failure_details, strategy
            )

            # Update shop status
            await self._update_shop_status(shop_id, failure_type, strategy)

            # Apply service limitations
            await self._apply_service_limitations(shop_id, strategy)

            # Send notifications
            await self._send_notifications(shop_id, failure_type, strategy)

            # Schedule retry attempts
            await self._schedule_retry_attempts(shop_id, failure_type, strategy)

            # Create billing event
            await self._create_billing_event(shop_id, failure_type, failure_details)

            logger.info(f"Successfully handled payment failure for shop {shop_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling payment failure for shop {shop_id}: {e}")
            return False

    async def _create_failure_record(
        self,
        shop_id: str,
        failure_type: PaymentFailureType,
        failure_details: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> str:
        """Create a payment failure record"""
        try:
            failure_record = await self.prisma.paymentfailure.create(
                {
                    "data": {
                        "shopId": shop_id,
                        "failureType": failure_type.value,
                        "failureDetails": failure_details,
                        "strategy": strategy,
                        "status": "active",
                        "gracePeriodDays": strategy["grace_period_days"],
                        "retrySchedule": strategy["retry_schedule"],
                        "serviceImpact": strategy["service_impact"].value,
                        "createdAt": datetime.utcnow(),
                        "updatedAt": datetime.utcnow(),
                    }
                }
            )

            logger.info(
                f"Created payment failure record {failure_record.id} for shop {shop_id}"
            )
            return failure_record.id

        except Exception as e:
            logger.error(f"Error creating payment failure record: {e}")
            return ""

    async def _update_shop_status(
        self, shop_id: str, failure_type: PaymentFailureType, strategy: Dict[str, Any]
    ):
        """Update shop payment status"""
        try:
            await self.prisma.shop.update_many(
                where={"id": shop_id},
                data={
                    "paymentStatus": "failed",
                    "paymentFailureType": failure_type.value,
                    "paymentFailureAt": datetime.utcnow(),
                    "serviceImpact": strategy["service_impact"].value,
                    "gracePeriodEndsAt": datetime.utcnow()
                    + timedelta(days=strategy["grace_period_days"]),
                    "updatedAt": datetime.utcnow(),
                },
            )

            logger.info(f"Updated shop status for {shop_id}")

        except Exception as e:
            logger.error(f"Error updating shop status: {e}")

    async def _apply_service_limitations(self, shop_id: str, strategy: Dict[str, Any]):
        """Apply service limitations based on failure type"""
        try:
            service_impact = strategy["service_impact"]

            if service_impact == ServiceImpact.LIMITED_FUNCTIONALITY:
                await self._limit_advanced_features(shop_id)
            elif service_impact == ServiceImpact.USAGE_LIMITED:
                await self._limit_usage_tracking(shop_id)
            elif service_impact == ServiceImpact.SERVICE_SUSPENDED:
                await self._suspend_service(shop_id)

            logger.info(
                f"Applied service limitations for shop {shop_id}: {service_impact.value}"
            )

        except Exception as e:
            logger.error(f"Error applying service limitations: {e}")

    async def _limit_advanced_features(self, shop_id: str):
        """Limit advanced features but keep core functionality"""
        try:
            # Update shop configuration to disable advanced features
            await self.prisma.shop.update_many(
                where={"id": shop_id},
                data={
                    "configuration": {
                        "advanced_features_enabled": False,
                        "analytics_enabled": False,
                        "custom_recommendations": False,
                        "a_b_testing": False,
                        "limited_functionality": True,
                    }
                },
            )

            logger.info(f"Limited advanced features for shop {shop_id}")

        except Exception as e:
            logger.error(f"Error limiting advanced features: {e}")

    async def _limit_usage_tracking(self, shop_id: str):
        """Limit usage tracking to prevent exceeding cap"""
        try:
            # Update billing plan to limit usage tracking
            await self.prisma.billingplan.update_many(
                where={"shopId": shop_id, "status": "active"},
                data={
                    "configuration": {
                        "usage_tracking_limited": True,
                        "max_daily_usage": 10,  # Limit daily usage
                        "usage_warning_threshold": 0.8,  # Warn at 80% of cap
                    }
                },
            )

            logger.info(f"Limited usage tracking for shop {shop_id}")

        except Exception as e:
            logger.error(f"Error limiting usage tracking: {e}")

    async def _suspend_service(self, shop_id: str):
        """Suspend service completely"""
        try:
            await self.prisma.shop.update_many(
                where={"id": shop_id},
                data={
                    "isActive": False,
                    "suspendedAt": datetime.utcnow(),
                    "suspensionReason": "payment_failure",
                    "serviceImpact": "suspended",
                },
            )

            logger.info(f"Suspended service for shop {shop_id}")

        except Exception as e:
            logger.error(f"Error suspending service: {e}")

    async def _send_notifications(
        self, shop_id: str, failure_type: PaymentFailureType, strategy: Dict[str, Any]
    ):
        """Send failure notifications"""
        try:
            notifications = strategy["notifications"]

            for notification_type in notifications:
                await self._send_notification(
                    shop_id, failure_type, notification_type, strategy
                )

            logger.info(f"Sent notifications for shop {shop_id}: {notifications}")

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    async def _send_notification(
        self,
        shop_id: str,
        failure_type: PaymentFailureType,
        notification_type: str,
        strategy: Dict[str, Any],
    ):
        """Send a specific notification"""
        try:
            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id}, select={"email": True, "shopDomain": True}
            )

            if not shop:
                logger.error(f"Shop {shop_id} not found for notification")
                return

            # Create notification content
            notification_content = self._create_notification_content(
                failure_type, strategy
            )

            # Send notification based on type
            if notification_type == "email":
                await self._send_email_notification(shop.email, notification_content)
            elif notification_type == "in_app":
                await self._send_in_app_notification(shop_id, notification_content)
            elif notification_type == "sms":
                await self._send_sms_notification(shop_id, notification_content)

            logger.info(f"Sent {notification_type} notification to shop {shop_id}")

        except Exception as e:
            logger.error(f"Error sending {notification_type} notification: {e}")

    def _create_notification_content(
        self, failure_type: PaymentFailureType, strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create notification content based on failure type"""
        content_templates = {
            PaymentFailureType.INSUFFICIENT_FUNDS: {
                "subject": "Payment Failed - Insufficient Funds",
                "message": "Your payment failed due to insufficient funds. Please update your payment method to continue using Better Bundle.",
                "action_required": "Update Payment Method",
                "urgency": "high",
            },
            PaymentFailureType.DECLINED_CARD: {
                "subject": "Payment Declined - Card Issue",
                "message": "Your payment was declined. Please check your card details or try a different payment method.",
                "action_required": "Update Payment Method",
                "urgency": "high",
            },
            PaymentFailureType.EXPIRED_CARD: {
                "subject": "Payment Failed - Expired Card",
                "message": "Your payment failed because your card has expired. Please update your payment method.",
                "action_required": "Update Payment Method",
                "urgency": "medium",
            },
            PaymentFailureType.CAPPED_AMOUNT_REACHED: {
                "subject": "Usage Limit Reached",
                "message": "You've reached your monthly usage limit. Upgrade your plan to continue using Better Bundle.",
                "action_required": "Upgrade Plan",
                "urgency": "medium",
            },
            PaymentFailureType.SUBSCRIPTION_CANCELLED: {
                "subject": "Subscription Cancelled",
                "message": "Your Better Bundle subscription has been cancelled. Renew to continue using our services.",
                "action_required": "Renew Subscription",
                "urgency": "high",
            },
        }

        return content_templates.get(
            failure_type,
            {
                "subject": "Payment Issue",
                "message": "There was an issue with your payment. Please contact support.",
                "action_required": "Contact Support",
                "urgency": "medium",
            },
        )

    async def _schedule_retry_attempts(
        self, shop_id: str, failure_type: PaymentFailureType, strategy: Dict[str, Any]
    ):
        """Schedule retry attempts"""
        try:
            retry_schedule = strategy["retry_schedule"]

            for retry_day in retry_schedule:
                retry_date = datetime.utcnow() + timedelta(days=retry_day)

                # Create retry job (integrate with your job queue)
                await self._create_retry_job(
                    shop_id, retry_date, retry_day, failure_type
                )

            logger.info(
                f"Scheduled {len(retry_schedule)} retry attempts for shop {shop_id}"
            )

        except Exception as e:
            logger.error(f"Error scheduling retry attempts: {e}")

    async def _create_retry_job(
        self,
        shop_id: str,
        retry_date: datetime,
        retry_day: int,
        failure_type: PaymentFailureType,
    ):
        """Create a retry job"""
        try:
            # This would integrate with your job queue system
            # For now, we'll just log it
            logger.info(f"Scheduled retry job for shop {shop_id} on {retry_date}")

        except Exception as e:
            logger.error(f"Error creating retry job: {e}")

    async def recover_from_failure(self, shop_id: str) -> bool:
        """
        Recover from payment failure when payment is successful.

        Args:
            shop_id: Shop ID

        Returns:
            True if recovered successfully
        """
        try:
            # Update shop status
            await self.prisma.shop.update_many(
                where={"id": shop_id},
                data={
                    "paymentStatus": "active",
                    "paymentFailureType": None,
                    "paymentFailureAt": None,
                    "serviceImpact": "none",
                    "gracePeriodEndsAt": None,
                    "isActive": True,
                    "suspendedAt": None,
                    "suspensionReason": None,
                    "updatedAt": datetime.utcnow(),
                },
            )

            # Restore service functionality
            await self._restore_service_functionality(shop_id)

            # Create recovery event
            await self._create_recovery_event(shop_id)

            logger.info(
                f"Successfully recovered from payment failure for shop {shop_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error recovering from payment failure: {e}")
            return False

    async def _restore_service_functionality(self, shop_id: str):
        """Restore full service functionality"""
        try:
            # Update shop configuration to restore features
            await self.prisma.shop.update_many(
                where={"id": shop_id},
                data={
                    "configuration": {
                        "advanced_features_enabled": True,
                        "analytics_enabled": True,
                        "custom_recommendations": True,
                        "a_b_testing": True,
                        "limited_functionality": False,
                    }
                },
            )

            # Update billing plan to restore usage tracking
            await self.prisma.billingplan.update_many(
                where={"shopId": shop_id, "status": "active"},
                data={
                    "configuration": {
                        "usage_tracking_limited": False,
                        "max_daily_usage": None,
                        "usage_warning_threshold": 0.9,
                    }
                },
            )

            logger.info(f"Restored service functionality for shop {shop_id}")

        except Exception as e:
            logger.error(f"Error restoring service functionality: {e}")
