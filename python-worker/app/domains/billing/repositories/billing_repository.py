"""
Billing Repository for database operations
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from prisma import Prisma
from prisma.models import (
    BillingPlan,
    BillingInvoice,
    BillingEvent,
    UserInteraction,
    UserSession,
    PurchaseAttribution,
)

from ..models.attribution_models import (
    AttributionResult,
    AttributionBreakdown,
    AttributionMetrics,
    ExtensionType,
    AttributionType,
    AttributionStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class BillingPeriod:
    """Billing period data"""

    start_date: datetime
    end_date: datetime
    cycle: str  # 'monthly', 'quarterly', 'annually'


class BillingRepository:
    """
    Repository for billing-related database operations.
    """

    def __init__(self, prisma: Prisma):
        self.prisma = prisma

    # ============= SHOP OPERATIONS =============

    async def get_shop(self, shop_id: str) -> Optional[Any]:
        """
        Get shop information including currency.

        Args:
            shop_id: Shop ID

        Returns:
            Shop object or None
        """
        try:
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id},
                select={
                    "id": True,
                    "shopDomain": True,
                    "currencyCode": True,
                    "isActive": True,
                },
            )
            return shop
        except Exception as e:
            logger.error(f"Error getting shop {shop_id}: {e}")
            return None

    # ============= BILLING PLANS =============

    async def create_billing_plan(
        self,
        shop_id: str,
        shop_domain: str,
        plan_name: str,
        plan_type: str,
        configuration: Dict[str, Any],
    ) -> BillingPlan:
        """Create a new billing plan for a shop."""
        try:
            plan = await self.prisma.billingplan.create(
                {
                    "shopId": shop_id,
                    "shopDomain": shop_domain,
                    "name": plan_name,
                    "type": plan_type,
                    "status": "active",
                    "configuration": configuration,
                    "effectiveFrom": datetime.utcnow(),
                }
            )

            # Create billing event
            await self.create_billing_event(
                shop_id=shop_id,
                event_type="plan_created",
                data={"plan_id": plan.id, "plan_type": plan_type},
                metadata={"created_by": "system"},
            )

            logger.info(f"Created billing plan {plan.id} for shop {shop_id}")
            return plan

        except Exception as e:
            logger.error(f"Error creating billing plan for shop {shop_id}: {e}")
            raise

    async def get_billing_plan(self, shop_id: str) -> Optional[BillingPlan]:
        """Get active billing plan for a shop."""
        try:
            plan = await self.prisma.billingplan.find_first(
                where={"shopId": shop_id, "status": "active"},
                order={"effectiveFrom": "desc"},
            )
            return plan
        except Exception as e:
            logger.error(f"Error getting billing plan for shop {shop_id}: {e}")
            return None

    async def update_billing_plan(
        self, plan_id: str, updates: Dict[str, Any]
    ) -> Optional[BillingPlan]:
        """Update billing plan."""
        try:
            plan = await self.prisma.billingplan.update(
                where={"id": plan_id}, data=updates
            )

            # Create billing event
            await self.create_billing_event(
                shop_id=plan.shopId,
                event_type="plan_updated",
                data={"plan_id": plan_id, "updates": updates},
                metadata={"updated_by": "system"},
            )

            logger.info(f"Updated billing plan {plan_id}")
            return plan

        except Exception as e:
            logger.error(f"Error updating billing plan {plan_id}: {e}")
            return None

    async def create_trial_billing_plan(
        self, shop_id: str, shop_domain: str, trial_threshold: float = 200.00
    ) -> Dict[str, Any]:
        """
        Create a trial billing plan for a new shop installation.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            trial_threshold: Revenue threshold for trial (default $200)

        Returns:
            Created billing plan information
        """
        try:
            logger.info(f"Creating trial billing plan for shop {shop_id}")

            # Create trial billing plan
            billing_plan = await self.prisma.billingplan.create(
                {
                    "shopId": shop_id,
                    "shopDomain": shop_domain,
                    "name": "Free Trial Plan",
                    "type": "revenue_share",
                    "status": "active",
                    "configuration": {
                        "revenue_share_rate": 0.03,
                        "trial_threshold": trial_threshold,
                        "trial_active": True,
                    },
                    "effectiveFrom": datetime.utcnow(),
                    "isTrialActive": True,
                    "trialThreshold": trial_threshold,
                    "trialRevenue": 0.0,
                }
            )

            # Create billing event
            await self.create_billing_event(
                shop_id=shop_id,
                event_type="trial_started",
                data={
                    "trial_threshold": trial_threshold,
                    "plan_id": billing_plan.id,
                },
                metadata={
                    "trial_type": "revenue_based",
                    "created_at": datetime.utcnow().isoformat(),
                },
            )

            logger.info(
                f"Created trial billing plan {billing_plan.id} for shop {shop_id}"
            )

            return {
                "plan_id": billing_plan.id,
                "name": billing_plan.name,
                "type": billing_plan.type,
                "status": billing_plan.status,
                "trial_threshold": float(billing_plan.trialThreshold),
                "trial_active": billing_plan.isTrialActive,
                "created_at": billing_plan.createdAt.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating trial billing plan for shop {shop_id}: {e}")
            raise

    async def get_shop_attribution_data(
        self, shop_id: str, period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Get attribution data for billing calculation."""
        try:
            # Get purchase attributions for the period
            attributions = await self.prisma.purchaseattribution.find_many(
                where={
                    "shopId": shop_id,
                    "purchaseAt": {"gte": period_start, "lte": period_end},
                }
            )

            # Get user interactions for the period
            interactions = await self.prisma.userinteraction.find_many(
                where={
                    "shopId": shop_id,
                    "createdAt": {"gte": period_start, "lte": period_end},
                }
            )

            # Calculate metrics
            total_revenue = sum(float(attr.totalRevenue) for attr in attributions)
            attributed_revenue = sum(float(attr.totalRevenue) for attr in attributions)
            total_interactions = len(interactions)
            total_conversions = len(attributions)

            # Extension metrics
            extension_metrics = {}
            for extension in ["venus", "phoenix", "apollo", "atlas"]:
                extension_attributions = [
                    attr for attr in attributions if extension in attr.attributedRevenue
                ]
                extension_revenue = sum(
                    float(attr.attributedRevenue.get(extension, 0))
                    for attr in extension_attributions
                )
                extension_interactions = len(
                    [i for i in interactions if i.extensionType == extension]
                )

                extension_metrics[extension] = {
                    "revenue": extension_revenue,
                    "interactions": extension_interactions,
                    "conversions": len(extension_attributions),
                    "conversion_rate": (
                        len(extension_attributions) / extension_interactions
                        if extension_interactions > 0
                        else 0
                    ),
                }

            return {
                "total_revenue": total_revenue,
                "attributed_revenue": attributed_revenue,
                "billable_revenue": attributed_revenue,  # Same as attributed for now
                "total_interactions": total_interactions,
                "total_conversions": total_conversions,
                "conversion_rate": (
                    total_conversions / total_interactions
                    if total_interactions > 0
                    else 0
                ),
                "average_order_value": (
                    total_revenue / total_conversions if total_conversions > 0 else 0
                ),
                "extension_metrics": extension_metrics,
            }

        except Exception as e:
            logger.error(f"Error getting attribution data for shop {shop_id}: {e}")
            return {}

    # ============= BILLING INVOICES =============

    async def create_billing_invoice(
        self,
        shop_id: str,
        plan_id: str,
        metrics_id: str,
        period: BillingPeriod,
        invoice_data: Dict[str, Any],
    ) -> BillingInvoice:
        """Create a billing invoice."""
        try:
            # Generate invoice number
            invoice_number = f"BB-{shop_id[:8]}-{period.start_date.strftime('%Y%m')}-{datetime.utcnow().strftime('%H%M%S')}"

            invoice = await self.prisma.billinginvoice.create(
                {
                    "shopId": shop_id,
                    "planId": plan_id,
                    "invoiceNumber": invoice_number,
                    "status": "pending",
                    "subtotal": float(invoice_data.get("subtotal", 0)),
                    "taxes": float(invoice_data.get("taxes", 0)),
                    "discounts": float(invoice_data.get("discounts", 0)),
                    "total": float(invoice_data.get("total", 0)),
                    "currency": invoice_data.get("currency", "USD"),
                    "periodStart": period.start_date,
                    "periodEnd": period.end_date,
                    "metricsId": metrics_id,
                    "dueDate": datetime.utcnow()
                    + timedelta(days=30),  # 30 days from now
                }
            )

            # Create billing event
            await self.create_billing_event(
                shop_id=shop_id,
                event_type="invoice_generated",
                data={"invoice_id": invoice.id, "invoice_number": invoice_number},
                metadata={"amount": invoice_data.get("total", 0)},
            )

            logger.info(f"Created billing invoice {invoice.id} for shop {shop_id}")
            return invoice

        except Exception as e:
            logger.error(f"Error creating billing invoice for shop {shop_id}: {e}")
            raise

    async def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        payment_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[BillingInvoice]:
        """Update invoice status."""
        try:
            update_data = {"status": status}

            if status == "paid" and payment_data:
                update_data.update(
                    {
                        "paidAt": datetime.utcnow(),
                        "paymentMethod": payment_data.get("payment_method"),
                        "paymentReference": payment_data.get("payment_reference"),
                    }
                )

            invoice = await self.prisma.billinginvoice.update(
                where={"id": invoice_id}, data=update_data
            )

            # Create billing event
            await self.create_billing_event(
                shop_id=invoice.shopId,
                event_type=f"payment_{status}",
                data={"invoice_id": invoice_id, "status": status},
                metadata=payment_data or {},
            )

            logger.info(f"Updated invoice {invoice_id} status to {status}")
            return invoice

        except Exception as e:
            logger.error(f"Error updating invoice {invoice_id} status: {e}")
            return None

    async def get_shop_invoices(
        self, shop_id: str, limit: int = 50, offset: int = 0
    ) -> List[BillingInvoice]:
        """Get invoices for a shop."""
        try:
            invoices = await self.prisma.billinginvoice.find_many(
                where={"shopId": shop_id},
                order={"createdAt": "desc"},
                take=limit,
                skip=offset,
            )
            return invoices
        except Exception as e:
            logger.error(f"Error getting invoices for shop {shop_id}: {e}")
            return []

    # ============= BILLING EVENTS =============

    async def create_billing_event(
        self,
        shop_id: str,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BillingEvent:
        """Create a billing event for audit trail."""
        try:
            event = await self.prisma.billingevent.create(
                {
                    "shopId": shop_id,
                    "type": event_type,
                    "data": data,
                    "metadata": metadata or {},
                    "occurredAt": datetime.utcnow(),
                }
            )

            logger.debug(f"Created billing event {event.id} for shop {shop_id}")
            return event

        except Exception as e:
            logger.error(f"Error creating billing event for shop {shop_id}: {e}")
            raise

    async def get_billing_events(
        self,
        shop_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BillingEvent]:
        """Get billing events for a shop."""
        try:
            where_conditions = {"shopId": shop_id}
            if event_type:
                where_conditions["type"] = event_type

            events = await self.prisma.billingevent.find_many(
                where=where_conditions,
                order={"occurredAt": "desc"},
                take=limit,
                skip=offset,
            )
            return events
        except Exception as e:
            logger.error(f"Error getting billing events for shop {shop_id}: {e}")
            return []

    # ============= UTILITY METHODS =============

    async def get_shops_for_billing(self) -> List[str]:
        """Get list of shop IDs that need billing processing."""
        try:
            # Get shops with active billing plans
            plans = await self.prisma.billingplan.find_many(where={"status": "active"})

            shop_ids = [plan.shopId for plan in plans]
            logger.info(f"Found {len(shop_ids)} shops for billing processing")
            return shop_ids

        except Exception as e:
            logger.error(f"Error getting shops for billing: {e}")
            return []

    async def get_billing_periods_for_shop(
        self, shop_id: str, cycle: str = "monthly"
    ) -> List[BillingPeriod]:
        """Get billing periods that need processing for a shop."""
        try:
            periods = []

            if cycle == "monthly":
                # Get last 3 months
                for i in range(3):
                    period_start = datetime.utcnow().replace(day=1) - timedelta(
                        days=30 * i
                    )
                    period_end = period_start + timedelta(days=30)
                    periods.append(
                        BillingPeriod(
                            start_date=period_start,
                            end_date=period_end,
                            cycle="monthly",
                        )
                    )

            return periods

        except Exception as e:
            logger.error(f"Error getting billing periods for shop {shop_id}: {e}")
            return []
