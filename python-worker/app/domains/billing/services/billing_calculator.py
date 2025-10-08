"""
Billing Calculator for Pay-as-Performance Model

This service calculates billing fees based on performance metrics and applies
performance tiers and discounts.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple

from app.shared.helpers import now_utc
from app.core.database.models import SubscriptionStatus

from ..models.attribution_models import AttributionMetrics
from ..repositories.billing_repository_v2 import BillingRepositoryV2, BillingPeriod

logger = logging.getLogger(__name__)


class BillingCalculator:
    """
    Calculates billing fees based on performance metrics.
    """

    def __init__(self, billing_repository: BillingRepositoryV2):
        self.billing_repository = billing_repository

        # Default billing configuration
        self.default_config = {
            "revenue_share_rate": 0.03,  # 3% base rate
            "performance_tiers": [
                {
                    "name": "Tier 1",
                    "min_revenue": 0,
                    "max_revenue": 5000,
                    "rate": 0.03,  # 3%
                },
                {
                    "name": "Tier 2",
                    "min_revenue": 5000,
                    "max_revenue": 25000,
                    "rate": 0.025,  # 2.5%
                },
                {
                    "name": "Tier 3",
                    "min_revenue": 25000,
                    "max_revenue": None,  # No upper limit
                    "rate": 0.02,  # 2%
                },
            ],
            "minimum_fee": 0,  # No minimum fee
            "maximum_fee": None,  # No maximum fee
            "currency": "USD",
        }

    async def calculate_billing_fee(
        self, shop_id: str, period: BillingPeriod, metrics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate billing fee for a shop for a given period.

        Args:
            shop_id: Shop ID
            period: Billing period
            metrics_data: Performance metrics data

        Returns:
            Dictionary with billing calculation results
        """
        try:
            logger.info(
                f"Calculating billing fee for shop {shop_id} for period {period.start_date} to {period.end_date}"
            )

            # Get shop currency first
            shop = await self.billing_repository.get_shop(shop_id)
            store_currency = shop.currencyCode if shop and shop.currencyCode else "USD"
            logger.info(f"Using currency {store_currency} for shop {shop_id}")

            # Get shop subscription for shop
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.warning(f"No shop subscription found for shop {shop_id}")
                return self._create_empty_billing_result(
                    shop_id, period, store_currency
                )

            # Check if shop is in trial period
            trial_status = await self._check_trial_status(
                shop_subscription, metrics_data
            )

            # Handle trial completion if threshold reached
            if trial_status.get("trial_just_completed", False):
                await self._handle_trial_completion(
                    shop_id, shop_subscription, trial_status
                )

            if trial_status["is_trial_active"]:
                logger.info(
                    f"Shop {shop_id} is in trial period. Revenue: ${trial_status['current_revenue']}, Threshold: ${trial_status['threshold']}"
                )
                return self._create_trial_billing_result(
                    shop_id, period, trial_status, store_currency
                )

            # Get plan configuration from pricing tier
            pricing_tier = shop_subscription.pricing_tier
            plan_config = (
                pricing_tier.tier_metadata
                if pricing_tier and pricing_tier.tier_metadata
                else self.default_config
            )

            # Calculate base fee
            base_fee = self._calculate_base_fee(metrics_data, plan_config)

            # Apply performance tiers
            tiered_fee = self._apply_performance_tiers(
                base_fee, metrics_data, plan_config
            )

            # Apply discounts
            discounted_fee = self._apply_discounts(
                tiered_fee, metrics_data, plan_config
            )

            # Apply minimum/maximum limits
            final_fee = self._apply_fee_limits(discounted_fee, plan_config)

            # Create billing result
            billing_result = {
                "shop_id": shop_id,
                "subscription_id": shop_subscription.id,
                "currency": store_currency,
                "period": {
                    "start_date": period.start_date,
                    "end_date": period.end_date,
                    "cycle": period.cycle,
                },
                "metrics": metrics_data,
                "calculation": {
                    "base_fee": float(base_fee),
                    "tiered_fee": float(tiered_fee),
                    "discounted_fee": float(discounted_fee),
                    "final_fee": float(final_fee),
                    "currency": store_currency,
                },
                "breakdown": self._create_fee_breakdown(metrics_data, plan_config),
                "calculated_at": now_utc().isoformat(),
            }

            logger.info(f"Calculated billing fee for shop {shop_id}: ${final_fee}")
            return billing_result

        except Exception as e:
            logger.error(f"Error calculating billing fee for shop {shop_id}: {e}")
            return self._create_error_billing_result(shop_id, period, str(e))

    def _calculate_base_fee(
        self, metrics_data: Dict[str, Any], plan_config: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate base fee using revenue share rate.

        Args:
            metrics_data: Performance metrics
            plan_config: Plan configuration

        Returns:
            Base fee amount
        """
        attributed_revenue = Decimal(str(metrics_data.get("attributed_revenue", 0)))
        revenue_share_rate = Decimal(str(plan_config.get("revenue_share_rate", 0.03)))

        base_fee = attributed_revenue * revenue_share_rate

        logger.debug(
            f"Base fee calculation: ${attributed_revenue} × {revenue_share_rate} = ${base_fee}"
        )
        return base_fee

    def _apply_performance_tiers(
        self,
        base_fee: Decimal,
        metrics_data: Dict[str, Any],
        plan_config: Dict[str, Any],
    ) -> Decimal:
        """
        Apply performance tier rates.

        Args:
            base_fee: Base fee amount
            metrics_data: Performance metrics
            plan_config: Plan configuration

        Returns:
            Fee after applying performance tiers
        """
        attributed_revenue = Decimal(str(metrics_data.get("attributed_revenue", 0)))
        performance_tiers = plan_config.get("performance_tiers", [])

        if not performance_tiers:
            return base_fee

        tiered_fee = Decimal("0")

        for tier in performance_tiers:
            min_revenue = Decimal(str(tier.get("min_revenue", 0)))
            max_revenue = (
                Decimal(str(tier.get("max_revenue", float("inf"))))
                if tier.get("max_revenue")
                else Decimal("inf")
            )
            rate = Decimal(str(tier.get("rate", 0.03)))

            # Calculate revenue in this tier
            tier_revenue_start = max(attributed_revenue, min_revenue)
            tier_revenue_end = min(attributed_revenue, max_revenue)

            if tier_revenue_start <= tier_revenue_end:
                tier_revenue = tier_revenue_end - tier_revenue_start
                tier_fee = tier_revenue * rate
                tiered_fee += tier_fee

                logger.debug(
                    f"Tier {tier['name']}: ${tier_revenue} × {rate} = ${tier_fee}"
                )

        logger.debug(f"Tiered fee: ${tiered_fee}")
        return tiered_fee

    def _apply_discounts(
        self, fee: Decimal, metrics_data: Dict[str, Any], plan_config: Dict[str, Any]
    ) -> Decimal:
        """
        Apply discounts based on performance.

        Args:
            fee: Current fee amount
            metrics_data: Performance metrics
            plan_config: Plan configuration

        Returns:
            Fee after applying discounts
        """
        # For now, no discounts are applied
        # This can be extended to include:
        # - Volume discounts
        # - Performance bonuses
        # - Promotional discounts
        # - Early payment discounts

        return fee

    def _apply_fee_limits(self, fee: Decimal, plan_config: Dict[str, Any]) -> Decimal:
        """
        Apply minimum and maximum fee limits.

        Args:
            fee: Current fee amount
            plan_config: Plan configuration

        Returns:
            Fee after applying limits
        """
        minimum_fee = Decimal(str(plan_config.get("minimum_fee", 0)))
        maximum_fee = (
            Decimal(str(plan_config.get("maximum_fee", float("inf"))))
            if plan_config.get("maximum_fee")
            else Decimal("inf")
        )

        # Apply minimum fee
        if fee < minimum_fee:
            fee = minimum_fee
            logger.debug(f"Applied minimum fee: ${fee}")

        # Apply maximum fee
        if fee > maximum_fee:
            fee = maximum_fee
            logger.debug(f"Applied maximum fee: ${fee}")

        return fee

    def _create_fee_breakdown(
        self, metrics_data: Dict[str, Any], plan_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create detailed fee breakdown.

        Args:
            metrics_data: Performance metrics
            plan_config: Plan configuration

        Returns:
            Fee breakdown dictionary
        """
        attributed_revenue = Decimal(str(metrics_data.get("attributed_revenue", 0)))
        total_interactions = metrics_data.get("total_interactions", 0)
        total_conversions = metrics_data.get("total_conversions", 0)
        conversion_rate = metrics_data.get("conversion_rate", 0)

        # Extension breakdown
        extension_metrics = metrics_data.get("extension_metrics", {})
        extension_breakdown = {}

        for extension, metrics in extension_metrics.items():
            extension_revenue = Decimal(str(metrics.get("revenue", 0)))
            extension_rate = Decimal(str(plan_config.get("revenue_share_rate", 0.03)))
            extension_fee = extension_revenue * extension_rate

            extension_breakdown[extension] = {
                "revenue": float(extension_revenue),
                "rate": float(extension_rate),
                "fee": float(extension_fee),
                "interactions": metrics.get("interactions", 0),
                "conversions": metrics.get("conversions", 0),
                "conversion_rate": metrics.get("conversion_rate", 0),
            }

        return {
            "total_attributed_revenue": float(attributed_revenue),
            "total_interactions": total_interactions,
            "total_conversions": total_conversions,
            "conversion_rate": conversion_rate,
            "extension_breakdown": extension_breakdown,
            "performance_tiers": plan_config.get("performance_tiers", []),
            "applied_rate": float(plan_config.get("revenue_share_rate", 0.03)),
        }

    def _create_empty_billing_result(
        self, shop_id: str, period: BillingPeriod, currency: str = "USD"
    ) -> Dict[str, Any]:
        """Create empty billing result when no plan is found."""
        return {
            "shop_id": shop_id,
            "plan_id": None,
            "currency": currency,
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
            "calculated_at": now_utc().isoformat(),
            "error": "No billing plan found",
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
            "calculated_at": now_utc().isoformat(),
            "error": error_message,
        }

    async def calculate_shop_billing_summary(
        self, shop_id: str, months: int = 12
    ) -> Dict[str, Any]:
        """
        Calculate billing summary for a shop over multiple months.

        Args:
            shop_id: Shop ID
            months: Number of months to include

        Returns:
            Billing summary dictionary
        """
        try:
            logger.info(
                f"Calculating billing summary for shop {shop_id} for last {months} months"
            )

            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                return {"error": "No shop subscription found"}

            # Get billing periods
            periods = await self.billing_repository.get_billing_periods_for_shop(
                shop_id
            )

            monthly_summaries = []
            total_revenue = Decimal("0")
            total_fees = Decimal("0")

            for period in periods[:months]:  # Limit to requested months
                # Get metrics for period
                metrics_data = await self.billing_repository.get_shop_attribution_data(
                    shop_id, period.start_date, period.end_date
                )

                if metrics_data.get("attributed_revenue", 0) > 0:
                    # Calculate billing for period
                    billing_result = await self.calculate_billing_fee(
                        shop_id, period, metrics_data
                    )

                    monthly_summaries.append(
                        {
                            "period": period.__dict__,
                            "revenue": billing_result["metrics"].get(
                                "attributed_revenue", 0
                            ),
                            "fee": billing_result["calculation"]["final_fee"],
                            "currency": billing_result["calculation"]["currency"],
                        }
                    )

                    total_revenue += Decimal(
                        str(billing_result["metrics"].get("attributed_revenue", 0))
                    )
                    total_fees += Decimal(
                        str(billing_result["calculation"]["final_fee"])
                    )

            # Calculate summary statistics
            average_monthly_revenue = (
                total_revenue / len(monthly_summaries)
                if monthly_summaries
                else Decimal("0")
            )
            average_monthly_fee = (
                total_fees / len(monthly_summaries)
                if monthly_summaries
                else Decimal("0")
            )
            average_fee_rate = (
                (total_fees / total_revenue * 100)
                if total_revenue > 0
                else Decimal("0")
            )

            return {
                "shop_id": shop_id,
                "subscription_id": shop_subscription.id,
                "summary": {
                    "total_revenue": float(total_revenue),
                    "total_fees": float(total_fees),
                    "average_monthly_revenue": float(average_monthly_revenue),
                    "average_monthly_fee": float(average_monthly_fee),
                    "average_fee_rate": float(average_fee_rate),
                    "months_analyzed": len(monthly_summaries),
                },
                "monthly_breakdown": monthly_summaries,
                "calculated_at": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error calculating billing summary for shop {shop_id}: {e}")
            return {"error": str(e)}

    # ============= TRIAL LOGIC =============

    async def _check_trial_status(
        self, shop_subscription, metrics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if shop is still in trial period based on revenue threshold.

        Args:
            shop_subscription: Shop's subscription
            metrics_data: Current period metrics

        Returns:
            Trial status information
        """
        try:
            # Get current attributed revenue for this period
            current_revenue = Decimal(str(metrics_data.get("attributed_revenue", 0)))

            # Get trial information
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if not trial:
                return {
                    "is_trial_active": False,
                    "current_revenue": 0,
                    "threshold": 0,
                    "remaining_revenue": 0,
                    "trial_progress": 0,
                }

            trial_threshold = trial.threshold_amount

            # Check if trial is still active
            is_trial_active = (
                trial.status.value == "active" and current_revenue < trial_threshold
            )

            # Calculate remaining revenue needed
            remaining_revenue = max(Decimal("0"), trial_threshold - current_revenue)

            # Check if trial just completed (revenue threshold reached)
            trial_just_completed = (
                trial.status.value == "active" and current_revenue >= trial_threshold
            )

            return {
                "is_trial_active": is_trial_active,
                "current_revenue": float(current_revenue),
                "threshold": float(trial_threshold),
                "remaining_revenue": float(remaining_revenue),
                "trial_progress": (
                    float((current_revenue / trial_threshold) * 100)
                    if trial_threshold > 0
                    else 0
                ),
                "trial_just_completed": trial_just_completed,
            }

        except Exception as e:
            logger.error(f"Error checking trial status: {e}")
            return {
                "is_trial_active": False,
                "current_revenue": 0,
                "threshold": 0,
                "remaining_revenue": 0,
                "trial_progress": 0,
            }

    async def _handle_trial_completion(
        self, shop_id: str, shop_subscription, trial_status: Dict[str, Any]
    ) -> None:
        """
        Handle trial completion by updating subscription status and creating trial completion invoice.

        Args:
            shop_id: Shop ID
            shop_subscription: Current shop subscription
            trial_status: Trial status information
        """
        try:
            if trial_status.get("trial_just_completed", False):
                logger.info(
                    f"🎉 Trial completed for shop {shop_id}! Revenue: ${trial_status['current_revenue']}"
                )

                # Update trial status to completed
                await self.billing_repository.update_trial_revenue(
                    shop_subscription.id, Decimal(str(trial_status["current_revenue"]))
                )

                # Update shop subscription status to active
                await self.billing_repository.update_shop_subscription_status(
                    shop_subscription.id, SubscriptionStatus.ACTIVE
                )

                logger.info(
                    f"✅ Trial ended for shop {shop_id}. Normal billing begins."
                )

        except Exception as e:
            logger.error(f"Error handling trial completion for shop {shop_id}: {e}")

    def _create_trial_billing_result(
        self,
        shop_id: str,
        period: BillingPeriod,
        trial_status: Dict[str, Any],
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Create billing result for trial period (no charges).

        Args:
            shop_id: Shop ID
            period: Billing period
            trial_status: Trial status information
            currency: Store currency

        Returns:
            Trial billing result
        """
        return {
            "shop_id": shop_id,
            "currency": currency,
            "period": {
                "start_date": period.start_date,
                "end_date": period.end_date,
                "cycle": period.cycle,
            },
            "trial_status": trial_status,
            "calculation": {
                "base_fee": 0.0,
                "tiered_fee": 0.0,
                "discounted_fee": 0.0,
                "final_fee": 0.0,
                "currency": "USD",
                "trial_active": True,
            },
            "breakdown": {
                "trial_threshold": trial_status["threshold"],
                "current_revenue": trial_status["current_revenue"],
                "remaining_revenue": trial_status["remaining_revenue"],
                "trial_progress": trial_status["trial_progress"],
            },
            "calculated_at": now_utc().isoformat(),
        }
