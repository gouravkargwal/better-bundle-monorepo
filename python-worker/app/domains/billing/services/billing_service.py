"""
Main Billing Service - SQLAlchemy Version

This service orchestrates the entire billing process including attribution,
calculation, and invoice generation.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .attribution_engine import AttributionEngine, AttributionContext
from .billing_calculator import BillingCalculator
from .shopify_usage_billing_service import ShopifyUsageBillingService
from .notification_service import BillingNotificationService
from ..repositories.billing_repository import BillingRepository, BillingPeriod
from ..models.attribution_models import AttributionResult, PurchaseEvent
from app.core.database.models import (
    Shop,
    BillingPlan,
    BillingEvent,
)

logger = logging.getLogger(__name__)


class BillingService:
    """
    Main billing service that orchestrates the entire billing process.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepository(session)
        self.attribution_engine = AttributionEngine(session)
        self.billing_calculator = BillingCalculator(self.billing_repository)
        self.shopify_usage_billing_service = ShopifyUsageBillingService(
            session, self.billing_repository
        )
        self.notification_service = BillingNotificationService(session)

    # ============= ATTRIBUTION PROCESSING =============

    async def process_purchase_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """
        Process attribution for a purchase event.

        Args:
            purchase_event: Purchase event data

        Returns:
            Attribution result
        """
        try:
            logger.info(
                f"Processing attribution for purchase {purchase_event.order_id}"
            )

            # Create attribution context
            logger.info(f"🔍 Purchase event products: {purchase_event.products}")
            context = AttributionContext(
                shop_id=purchase_event.shop_id,
                customer_id=purchase_event.customer_id,
                session_id=purchase_event.session_id,
                order_id=purchase_event.order_id,
                purchase_amount=purchase_event.total_amount,
                purchase_products=purchase_event.products,
                purchase_time=purchase_event.created_at,
            )

            # Calculate attribution
            attribution_result = await self.attribution_engine.calculate_attribution(
                context
            )

            logger.info(
                f"Attribution processed for purchase {purchase_event.order_id}: "
                f"${attribution_result.total_attributed_revenue}"
            )

            # Update trial revenue in real-time if shop is in trial
            await self._update_trial_revenue(
                purchase_event.shop_id, attribution_result.total_attributed_revenue
            )

            return attribution_result

        except Exception as e:
            logger.error(
                f"Error processing attribution for purchase {purchase_event.order_id}: {e}"
            )
            raise

    # ============= TRIAL REVENUE UPDATES =============

    async def update_trial_revenue(self, shop_id: str, revenue_amount: Decimal):
        """Update trial revenue tracking"""
        try:
            # Find the billing plan
            stmt = select(BillingPlan).where(BillingPlan.shop_id == shop_id)
            result = await self.session.execute(stmt)
            billing_plan = result.scalar_one_or_none()

            if billing_plan:
                # Update revenue
                billing_plan.trial_revenue = (
                    billing_plan.trial_revenue or Decimal("0")
                ) + revenue_amount
                billing_plan.updated_at = datetime.utcnow()

                await self.session.commit()
                logger.info(
                    f"Updated trial revenue for shop {shop_id}: +${revenue_amount}"
                )
            else:
                logger.warning(f"No billing plan found for shop {shop_id}")

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating trial revenue for shop {shop_id}: {str(e)}")
            raise

    async def _update_trial_revenue(self, shop_id: str, revenue_amount: Decimal):
        """Internal method to update trial revenue"""
        await self.update_trial_revenue(shop_id, revenue_amount)

    async def _handle_trial_completion(
        self, shop_id: str, billing_plan: BillingPlan, final_revenue: float
    ) -> None:
        """
        Handle trial completion when threshold is reached.
        For usage-based billing, this stops all services and requires user consent.

        Args:
            shop_id: Shop ID
            billing_plan: Current billing plan
            final_revenue: Final trial revenue amount
        """
        try:
            # 1. STOP ALL SERVICES - Mark shop as inactive
            stmt = (
                update(Shop)
                .where(Shop.id == shop_id)
                .values(
                    is_active=False,
                    suspended_at=datetime.utcnow(),
                    suspension_reason="trial_completed_consent_required",
                    service_impact="suspended",
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.execute(stmt)

            # 2. Update billing plan to mark trial as completed
            current_config = billing_plan.configuration or {}
            updated_config = {
                **current_config,
                "trial_active": False,
                "trial_completed_at": datetime.utcnow().isoformat(),
                "trial_completion_revenue": final_revenue,
                "services_stopped": True,
                "consent_required": True,
                "subscription_required": True,
                "billing_suspended": True,
            }

            billing_plan.is_trial_active = False
            billing_plan.trial_revenue = Decimal(str(final_revenue))
            billing_plan.status = "suspended"
            billing_plan.configuration = updated_config
            billing_plan.updated_at = datetime.utcnow()

            # 3. Create billing event for trial completion
            trial_event = BillingEvent(
                shop_id=shop_id,
                type="trial_completed",
                occurred_at=datetime.utcnow(),
                data={
                    "final_revenue": final_revenue,
                    "completed_at": datetime.utcnow().isoformat(),
                    "services_stopped": True,
                    "consent_required": True,
                },
                metadata={
                    "trial_completion": True,
                    "final_revenue": final_revenue,
                    "services_stopped": True,
                    "consent_required": True,
                },
            )
            self.session.add(trial_event)

            # 4. Create service suspension event
            suspension_event = BillingEvent(
                shop_id=shop_id,
                type="service_suspended",
                occurred_at=datetime.utcnow(),
                data={
                    "reason": "trial_completed_consent_required",
                    "suspended_at": datetime.utcnow().isoformat(),
                    "requires_consent": True,
                },
                metadata={
                    "suspension_type": "trial_completion",
                    "consent_required": True,
                },
            )
            self.session.add(suspension_event)

            await self.session.commit()

            # Get shop currency for proper formatting
            shop_stmt = select(Shop).where(Shop.id == shop_id)
            shop_result = await self.session.execute(shop_stmt)
            shop = shop_result.scalar_one_or_none()

            currency = shop.currency_code if shop and shop.currency_code else "USD"
            currency_symbol = "₹" if currency == "INR" else "$"

            logger.info(
                f"🛑 Trial completed for shop {shop_id} with revenue {currency_symbol}{final_revenue}"
            )
            logger.info(
                f"🚫 Services stopped - user consent required for usage-based billing"
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error handling trial completion for shop {shop_id}: {e}")
            raise

    async def handle_trial_completion_with_consent(
        self, shop_id: str, capped_amount: float, billing_rate: float
    ) -> bool:
        """
        Handle user consent for trial completion and reactivate services with capped billing.

        Args:
            shop_id: Shop ID
            capped_amount: Maximum amount user agrees to be charged
            billing_rate: Billing rate (e.g., 3% for 0.03)

        Returns:
            True if consent processed successfully, False otherwise
        """
        try:
            logger.info(f"🔄 Processing trial completion consent for shop {shop_id}")
            logger.info(f"   Capped amount: ${capped_amount}")
            logger.info(f"   Billing rate: {billing_rate * 100}%")

            # 1. Reactivate shop services
            stmt = (
                update(Shop)
                .where(Shop.id == shop_id)
                .values(
                    is_active=True,
                    suspended_at=None,
                    suspension_reason=None,
                    service_impact=None,
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.execute(stmt)

            # 2. Update billing plan with consent and capped amount
            billing_plan_stmt = select(BillingPlan).where(
                BillingPlan.shop_id == shop_id, BillingPlan.status == "suspended"
            )
            result = await self.session.execute(billing_plan_stmt)
            billing_plan = result.scalar_one_or_none()

            if not billing_plan:
                logger.error(f"No suspended billing plan found for shop {shop_id}")
                await self.session.rollback()
                return False

            current_config = billing_plan.configuration or {}
            updated_config = {
                **current_config,
                "consent_given": True,
                "services_stopped": False,
                "consent_required": False,
                "subscription_required": False,
                "billing_suspended": False,
                "capped_amount": capped_amount,
                "billing_rate": billing_rate,
                "consent_given_at": datetime.utcnow().isoformat(),
            }

            billing_plan.status = "active"
            billing_plan.configuration = updated_config
            billing_plan.updated_at = datetime.utcnow()

            # 3. Create consent event
            consent_event = BillingEvent(
                shop_id=shop_id,
                type="trial_completed_with_consent",
                occurred_at=datetime.utcnow(),
                data={
                    "consent_given": True,
                    "capped_amount": capped_amount,
                    "billing_rate": billing_rate,
                    "consent_given_at": datetime.utcnow().isoformat(),
                },
                metadata={
                    "trial_completion": True,
                    "consent_given": True,
                    "capped_amount": capped_amount,
                },
            )
            self.session.add(consent_event)

            # 4. Create service reactivation event
            reactivation_event = BillingEvent(
                shop_id=shop_id,
                type="service_reactivated",
                occurred_at=datetime.utcnow(),
                data={
                    "reason": "trial_completion_consent_given",
                    "reactivated_at": datetime.utcnow().isoformat(),
                    "capped_amount": capped_amount,
                },
                metadata={
                    "reactivation_type": "trial_completion_consent",
                    "capped_amount": capped_amount,
                },
            )
            self.session.add(reactivation_event)

            await self.session.commit()

            logger.info(
                f"✅ Services reactivated for shop {shop_id} with capped billing"
            )
            logger.info(f"   Capped amount: ${capped_amount}")
            logger.info(f"   Billing rate: {billing_rate * 100}%")

            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Error handling trial completion consent for shop {shop_id}: {e}"
            )
            return False

    # ============= BILLING CALCULATION =============

    async def calculate_monthly_billing(
        self, shop_id: str, period: Optional[BillingPeriod] = None
    ) -> Dict[str, Any]:
        """
        Calculate monthly billing for a shop.

        Args:
            shop_id: Shop ID
            period: Billing period (defaults to previous month)

        Returns:
            Billing calculation result
        """
        try:
            # Use previous month if no period specified
            if not period:
                period = self._get_previous_month_period()

            logger.info(
                f"Calculating monthly billing for shop {shop_id} for period {period.start_date} to {period.end_date}"
            )

            # Get attribution data for the period
            metrics_data = await self.billing_repository.get_shop_attribution_data(
                shop_id, period.start_date, period.end_date
            )

            if not metrics_data or metrics_data.get("attributed_revenue", 0) == 0:
                logger.info(
                    f"No attributed revenue found for shop {shop_id} in period {period.start_date} to {period.end_date}"
                )
                return self._create_empty_billing_result(shop_id, period)

            # Calculate billing fee
            billing_result = await self.billing_calculator.calculate_billing_fee(
                shop_id, period, metrics_data
            )

            logger.info(
                f"Monthly billing calculated for shop {shop_id}: ${billing_result['calculation']['final_fee']}"
            )
            return billing_result

        except Exception as e:
            logger.error(f"Error calculating monthly billing for shop {shop_id}: {e}")
            return self._create_error_billing_result(
                shop_id, period or self._get_previous_month_period(), str(e)
            )

    async def process_monthly_billing_with_shopify(
        self, shop_id: str, period: Optional[BillingPeriod] = None
    ) -> Dict[str, Any]:
        """
        Process monthly billing and create Shopify charge.

        Args:
            shop_id: Shop ID
            period: Billing period (defaults to previous month)

        Returns:
            Billing processing result with Shopify charge
        """
        try:
            # Calculate billing
            billing_result = await self.calculate_monthly_billing(shop_id, period)

            if (
                billing_result.get("error")
                or billing_result["calculation"]["final_fee"] <= 0
            ):
                logger.info(f"No billing charge needed for shop {shop_id}")
                return billing_result

            # Record usage for usage-based billing
            usage_record = (
                await self.shopify_usage_billing_service.process_monthly_usage_billing(
                    shop_id, billing_result
                )
            )

            if usage_record:
                billing_result["usage_record"] = {
                    "id": usage_record.id,
                    "subscription_line_item_id": usage_record.subscription_line_item_id,
                    "description": usage_record.description,
                    "price": usage_record.price,
                    "created_at": usage_record.created_at,
                }

                logger.info(f"Recorded usage {usage_record.id} for shop {shop_id}")
            else:
                logger.error(f"Failed to record usage for shop {shop_id}")
                billing_result["usage_record_error"] = "Failed to record usage"

            return billing_result

        except Exception as e:
            logger.error(
                f"Error processing monthly billing with Shopify for shop {shop_id}: {e}"
            )
            return self._create_error_billing_result(
                shop_id, period or self._get_previous_month_period(), str(e)
            )

    async def process_all_shop_billing(self) -> Dict[str, Any]:
        """
        Process billing for all shops.

        Returns:
            Processing summary
        """
        try:
            logger.info("Starting billing processing for all shops")

            # Get all shops with active billing plans
            shop_ids = await self.billing_repository.get_shops_for_billing()

            if not shop_ids:
                logger.info("No shops found for billing processing")
                return {"processed_shops": 0, "total_fees": 0, "errors": []}

            # Process billing for each shop
            processed_shops = 0
            total_fees = Decimal("0")
            errors = []

            for shop_id in shop_ids:
                try:
                    billing_result = await self.calculate_monthly_billing(shop_id)

                    if billing_result.get("calculation"):
                        total_fees += Decimal(
                            str(billing_result["calculation"]["final_fee"])
                        )
                        processed_shops += 1

                except Exception as e:
                    error_msg = f"Error processing billing for shop {shop_id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            result = {
                "processed_shops": processed_shops,
                "total_shops": len(shop_ids),
                "total_fees": float(total_fees),
                "errors": errors,
                "processed_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Billing processing completed: {processed_shops}/{len(shop_ids)} shops processed, "
                f"total fees: ${total_fees}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing billing for all shops: {e}")
            return {"error": str(e)}

    async def process_all_shop_billing_with_shopify(self) -> Dict[str, Any]:
        """
        Process billing for all shops with Shopify integration.

        Returns:
            Processing summary with Shopify charges
        """
        try:
            logger.info(
                "Starting billing processing with Shopify integration for all shops"
            )

            # Get all shops with active billing plans
            shop_ids = await self.billing_repository.get_shops_for_billing()

            if not shop_ids:
                logger.info("No shops found for billing processing")
                return {
                    "processed_shops": 0,
                    "total_fees": 0,
                    "shopify_charges": 0,
                    "errors": [],
                }

            # Process billing for each shop
            processed_shops = 0
            total_fees = Decimal("0")
            shopify_charges_created = 0
            errors = []

            for shop_id in shop_ids:
                try:
                    billing_result = await self.process_monthly_billing_with_shopify(
                        shop_id
                    )

                    if billing_result.get("calculation"):
                        total_fees += Decimal(
                            str(billing_result["calculation"]["final_fee"])
                        )
                        processed_shops += 1

                        if billing_result.get("shopify_charge"):
                            shopify_charges_created += 1

                except Exception as e:
                    error_msg = f"Error processing billing for shop {shop_id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            result = {
                "processed_shops": processed_shops,
                "total_shops": len(shop_ids),
                "total_fees": float(total_fees),
                "shopify_charges": shopify_charges_created,
                "errors": errors,
                "processed_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Billing processing with Shopify completed: {processed_shops}/{len(shop_ids)} shops processed, "
                f"total fees: ${total_fees}, Shopify charges: {shopify_charges_created}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing billing with Shopify for all shops: {e}")
            return {"error": str(e)}

    # ============= BILLING PLAN MANAGEMENT =============

    async def create_default_billing_plan(
        self, shop_id: str, shop_domain: str
    ) -> Dict[str, Any]:
        """
        Create default billing plan for a new shop.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain

        Returns:
            Created billing plan
        """
        try:
            logger.info(f"Creating default billing plan for shop {shop_id}")

            # Default configuration
            default_config = {
                "revenue_share_rate": 0.03,  # 3%
                "performance_tiers": [
                    {
                        "name": "Tier 1",
                        "min_revenue": 0,
                        "max_revenue": 5000,
                        "rate": 0.03,
                    },
                    {
                        "name": "Tier 2",
                        "min_revenue": 5000,
                        "max_revenue": 25000,
                        "rate": 0.025,
                    },
                    {
                        "name": "Tier 3",
                        "min_revenue": 25000,
                        "max_revenue": None,
                        "rate": 0.02,
                    },
                ],
                "minimum_fee": 0,
                "maximum_fee": None,
                "currency": "USD",
                "billing_cycle": "monthly",
            }

            # Create billing plan
            billing_plan = await self.billing_repository.create_billing_plan(
                shop_id=shop_id,
                shop_domain=shop_domain,
                plan_name="Pay-as-Performance Plan",
                plan_type="revenue_share",
                configuration=default_config,
            )

            logger.info(
                f"Created default billing plan {billing_plan.id} for shop {shop_id}"
            )

            return {
                "plan_id": billing_plan.id,
                "shop_id": shop_id,
                "plan_name": billing_plan.name,
                "plan_type": billing_plan.type,
                "configuration": billing_plan.configuration,
                "created_at": billing_plan.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating default billing plan for shop {shop_id}: {e}")
            raise

    async def get_shop_billing_summary(
        self, shop_id: str, months: int = 12
    ) -> Dict[str, Any]:
        """
        Get billing summary for a shop.

        Args:
            shop_id: Shop ID
            months: Number of months to include

        Returns:
            Billing summary
        """
        try:
            logger.info(
                f"Getting billing summary for shop {shop_id} for last {months} months"
            )

            # Get billing plan
            billing_plan = await self.billing_repository.get_billing_plan(shop_id)
            if not billing_plan:
                return {"error": "No billing plan found"}

            # Calculate billing summary
            summary = await self.billing_calculator.calculate_shop_billing_summary(
                shop_id, months
            )

            # Get recent invoices
            recent_invoices = await self.billing_repository.get_shop_invoices(
                shop_id, limit=5
            )

            # Get recent billing events
            recent_events = await self.billing_repository.get_billing_events(
                shop_id, limit=10
            )

            return {
                **summary,
                "billing_plan": {
                    "id": billing_plan.id,
                    "name": billing_plan.name,
                    "type": billing_plan.type,
                    "status": billing_plan.status,
                    "configuration": billing_plan.configuration,
                },
                "recent_invoices": [
                    {
                        "id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "status": invoice.status,
                        "total": float(invoice.total),
                        "currency": invoice.currency,
                        "period_start": invoice.period_start.isoformat(),
                        "period_end": invoice.period_end.isoformat(),
                        "created_at": invoice.created_at.isoformat(),
                    }
                    for invoice in recent_invoices
                ],
                "recent_events": [
                    {
                        "id": event.id,
                        "type": event.type,
                        "data": event.data,
                        "occurred_at": event.occurred_at.isoformat(),
                    }
                    for event in recent_events
                ],
            }

        except Exception as e:
            logger.error(f"Error getting billing summary for shop {shop_id}: {e}")
            return {"error": str(e)}

    # ============= NOTIFICATION HELPERS =============

    async def _send_invoice_notification(
        self, shop_id: str, invoice_data: Dict[str, Any]
    ) -> None:
        """Send invoice notification."""
        try:
            # Get shop contact email
            stmt = select(Shop.email).where(Shop.id == shop_id)
            result = await self.session.execute(stmt)
            shop = result.scalar_one_or_none()

            if not shop:
                logger.warning(f"No contact email found for shop {shop_id}")
                return

            # Send notification
            await self.notification_service.send_invoice_notification(
                shop_id, invoice_data, shop
            )

        except Exception as e:
            logger.error(f"Error sending invoice notification for shop {shop_id}: {e}")

    async def _send_payment_notification(
        self, shop_id: str, payment_data: Dict[str, Any], payment_status: str
    ) -> None:
        """Send payment notification."""
        try:
            # Get shop contact email
            stmt = select(Shop.email).where(Shop.id == shop_id)
            result = await self.session.execute(stmt)
            shop = result.scalar_one_or_none()

            if not shop:
                logger.warning(f"No contact email found for shop {shop_id}")
                return

            # Send notification
            await self.notification_service.send_payment_notification(
                shop_id, payment_data, shop, payment_status
            )

        except Exception as e:
            logger.error(f"Error sending payment notification for shop {shop_id}: {e}")

    async def _send_billing_summary_notification(
        self, shop_id: str, summary_data: Dict[str, Any]
    ) -> None:
        """Send billing summary notification."""
        try:
            # Get shop contact email
            stmt = select(Shop.email).where(Shop.id == shop_id)
            result = await self.session.execute(stmt)
            shop = result.scalar_one_or_none()

            if not shop:
                logger.warning(f"No contact email found for shop {shop_id}")
                return

            # Send notification
            await self.notification_service.send_billing_summary(
                shop_id, summary_data, shop
            )

        except Exception as e:
            logger.error(
                f"Error sending billing summary notification for shop {shop_id}: {e}"
            )

    # ============= UTILITY METHODS =============

    def _get_previous_month_period(self) -> BillingPeriod:
        """Get billing period for previous month."""
        now = datetime.utcnow()

        # First day of current month
        first_day_current = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        # First day of previous month
        if first_day_current.month == 1:
            first_day_previous = first_day_current.replace(
                year=first_day_current.year - 1, month=12
            )
        else:
            first_day_previous = first_day_current.replace(
                month=first_day_current.month - 1
            )

        # Last day of previous month
        if first_day_current.month == 1:
            last_day_previous = first_day_current.replace(day=1) - timedelta(days=1)
        else:
            last_day_previous = first_day_current - timedelta(days=1)

        return BillingPeriod(
            start_date=first_day_previous, end_date=last_day_previous, cycle="monthly"
        )

    def _create_empty_billing_result(
        self, shop_id: str, period: BillingPeriod
    ) -> Dict[str, Any]:
        """Create empty billing result."""
        return {
            "shop_id": shop_id,
            "plan_id": None,
            "period": {
                "start_date": period.start_date,
                "end_date": period.end_date,
                "cycle": period.cycle,
            },
            "metrics": {
                "total_revenue": 0,
                "attributed_revenue": 0,
                "billable_revenue": 0,
                "total_interactions": 0,
                "total_conversions": 0,
                "conversion_rate": 0,
                "average_order_value": 0,
                "extension_metrics": {},
            },
            "calculation": {
                "base_fee": 0.0,
                "tiered_fee": 0.0,
                "discounted_fee": 0.0,
                "final_fee": 0.0,
                "currency": "USD",
            },
            "breakdown": {},
            "calculated_at": datetime.utcnow().isoformat(),
            "message": "No attributed revenue found for this period",
        }

    def _create_error_billing_result(
        self, shop_id: str, period: BillingPeriod, error_message: str
    ) -> Dict[str, Any]:
        """Create error billing result."""
        return {
            "shop_id": shop_id,
            "plan_id": None,
            "period": {
                "start_date": period.start_date,
                "end_date": period.end_date,
                "cycle": period.cycle,
            },
            "metrics": {},
            "calculation": {
                "base_fee": 0.0,
                "tiered_fee": 0.0,
                "discounted_fee": 0.0,
                "final_fee": 0.0,
                "currency": "USD",
            },
            "breakdown": {},
            "calculated_at": datetime.utcnow().isoformat(),
            "error": error_message,
        }
