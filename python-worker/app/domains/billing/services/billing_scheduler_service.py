"""
Enhanced Billing Scheduler Service with Parallel Processing

This service handles scheduled billing calculations with improved concurrency,
parallel processing, and robust error handling for GitHub Actions cron jobs.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from app.shared.helpers import now_utc
from sqlalchemy import select, and_, func

from app.core.database.session import get_transaction_context
from app.core.database.models import Shop, ShopSubscription, BillingCycle
from app.core.database.models.enums import SubscriptionStatus
from app.core.logging import get_logger
from app.domains.billing.services.billing_service_v2 import BillingServiceV2
from app.domains.billing.repositories.billing_repository_v2 import (
    BillingRepositoryV2,
    BillingPeriod,
)
from app.core.config.settings import settings

logger = get_logger(__name__)


class BillingSchedulerService:
    """
    Enhanced service for scheduling and executing billing calculations with parallel processing.

    This service can be triggered by:
    1. GitHub Actions (webhook)
    2. Cron jobs
    3. Manual API calls
    4. Internal scheduling

    Features:
    - Parallel processing for multiple shops
    - Concurrency controls to prevent database overload
    - Robust error handling and retry mechanisms
    - Progress tracking and detailed logging
    """

    def __init__(self, max_concurrent_shops: int = 10, max_retries: int = 3):
        self.billing_service = None
        self.billing_repository = None
        self.max_concurrent_shops = max_concurrent_shops
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent_shops)

    async def initialize(self):
        """Initialize the billing service and repository - SESSION SAFE"""
        try:
            # ✅ FIX: Don't create services with closed sessions
            # Services will be created per-operation with fresh sessions
            self.billing_service = None
            self.billing_repository = None

            logger.info("Billing scheduler service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize billing scheduler service: {e}")
            raise

    async def process_monthly_billing(
        self,
        shop_ids: Optional[List[str]] = None,
        period: Optional[BillingPeriod] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Process monthly billing for specified shops or all active shops.

        Args:
            shop_ids: List of shop IDs to process (None for all active shops)
            period: Billing period (defaults to previous month)
            dry_run: If True, calculate but don't create invoices

        Returns:
            Processing results
        """
        try:
            logger.info(f"Starting monthly billing process - dry_run={dry_run}")

            # Initialize if not already done
            if not self.billing_service:
                await self.initialize()

            # Get shops to process
            shops_to_process = await self._get_shops_to_process(shop_ids)

            if not shops_to_process:
                logger.warning("No shops found for billing processing")
                return {
                    "status": "completed",
                    "message": "No shops found for processing",
                    "processed_shops": 0,
                    "total_revenue": 0.0,
                    "total_fees": 0.0,
                }

            # Use previous month if no period specified
            if not period:
                period = self._get_previous_month_period()

            logger.info(
                f"Processing billing for {len(shops_to_process)} shops for period {period.start_date} to {period.end_date}"
            )

            results = {
                "status": "processing",
                "period": {
                    "start_date": period.start_date.isoformat(),
                    "end_date": period.end_date.isoformat(),
                },
                "processed_shops": 0,
                "successful_shops": 0,
                "failed_shops": 0,
                "total_revenue": 0.0,
                "total_fees": 0.0,
                "shop_results": [],
                "errors": [],
                "started_at": now_utc().isoformat(),
                "dry_run": dry_run,
            }

            # Process shops in parallel with concurrency control
            logger.info(
                f"🚀 Starting parallel processing of {len(shops_to_process)} shops"
            )

            # Create tasks for parallel processing
            tasks = [
                self._process_shop_billing_with_retry(shop, period, dry_run)
                for shop in shops_to_process
            ]

            # Execute tasks with concurrency control
            shop_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(shop_results):
                shop = shops_to_process[i]
                results["processed_shops"] += 1

                if isinstance(result, Exception):
                    logger.error(f"❌ Exception processing shop {shop.id}: {result}")
                    results["failed_shops"] += 1
                    results["errors"].append({"shop_id": shop.id, "error": str(result)})
                elif result.get("success", False):
                    results["successful_shops"] += 1
                    results["total_revenue"] += result.get("attributed_revenue", 0.0)
                    results["total_fees"] += result.get("calculated_fee", 0.0)
                    results["shop_results"].append(result)
                else:
                    results["failed_shops"] += 1
                    results["errors"].append(
                        {
                            "shop_id": shop.id,
                            "error": result.get("error", "Unknown error"),
                        }
                    )
                    results["shop_results"].append(result)

            results["status"] = "completed"
            results["completed_at"] = now_utc().isoformat()

            logger.info(
                f"Monthly billing process completed: {results['successful_shops']} successful, {results['failed_shops']} failed"
            )

            return results

        except Exception as e:
            logger.error(f"Error in monthly billing process: {e}")
            return {
                "status": "error",
                "error": str(e),
                "completed_at": now_utc().isoformat(),
            }

    async def process_shop_billing(
        self,
        shop_id: str,
        period: Optional[BillingPeriod] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Process billing status for a specific shop."""
        try:
            if not period:
                period = self._get_previous_month_period()
            logger.info(
                f"Processing billing for shop {shop_id} - "
                f"period={period.start_date.date()}→{period.end_date.date()}, dry_run={dry_run}"
            )

            async with get_transaction_context() as session:
                billing_repository = BillingRepositoryV2(session)

                shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
                shop = shop_result.scalar_one_or_none()
                if not shop:
                    return {"success": False, "shop_id": shop_id, "error": "Shop not found"}
                if not shop.is_active:
                    return {"success": False, "shop_id": shop_id, "error": "Shop is not active"}

                shop_subscription = await billing_repository.get_shop_subscription(shop_id)
                if not shop_subscription:
                    return {"success": False, "shop_id": shop_id, "error": "No active subscription found"}

                current_cycle = await billing_repository.get_current_billing_cycle(
                    shop_subscription.id
                )

                return {
                    "success": True,
                    "shop_id": shop_id,
                    "shop_domain": shop.shop_domain,
                    "subscription_status": shop_subscription.status.value,
                    "usage_amount": float(current_cycle.usage_amount) if current_cycle else 0.0,
                    "cap_amount": float(current_cycle.current_cap_amount) if current_cycle else 0.0,
                    "dry_run": dry_run,
                }

        except Exception as e:
            logger.error(f"Error processing billing for shop {shop_id}: {e}")
            return {"success": False, "shop_id": shop_id, "error": str(e)}

    async def _get_shops_to_process(
        self, shop_ids: Optional[List[str]] = None
    ) -> List[Shop]:
        """Get shops with an active paid subscription."""
        async with get_transaction_context() as session:
            if shop_ids:
                query = select(Shop).where(
                    and_(Shop.id.in_(shop_ids), Shop.is_active == True)
                )
            else:
                # Only shops with an ACTIVE (paid) subscription
                active_shop_ids_subq = (
                    select(ShopSubscription.shop_id)
                    .where(
                        and_(
                            ShopSubscription.status == SubscriptionStatus.ACTIVE,
                            ShopSubscription.is_active == True,
                        )
                    )
                    .scalar_subquery()
                )
                query = select(Shop).where(
                    and_(
                        Shop.is_active == True,
                        Shop.id.in_(active_shop_ids_subq),
                    )
                )

            result = await session.execute(query)
            return result.scalars().all()

    async def _process_shop_billing_with_retry(
        self, shop: Shop, period: BillingPeriod, dry_run: bool
    ) -> Dict[str, Any]:
        """Process billing for a single shop with retry mechanism and concurrency control"""
        async with self.semaphore:  # Concurrency control
            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"🔄 Processing shop {shop.id} (attempt {attempt + 1}/{self.max_retries})"
                    )
                    result = await self._process_shop_billing_single(
                        shop, period, dry_run
                    )

                    if result.get("success", False):
                        logger.info(f"✅ Successfully processed shop {shop.id}")
                        return result
                    else:
                        logger.warning(
                            f"⚠️ Shop {shop.id} processing failed: {result.get('error', 'Unknown error')}"
                        )
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2**attempt)  # Exponential backoff
                        else:
                            return result

                except Exception as e:
                    logger.error(
                        f"❌ Exception processing shop {shop.id} (attempt {attempt + 1}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        return {"success": False, "shop_id": shop.id, "error": str(e)}

            return {
                "success": False,
                "shop_id": shop.id,
                "error": "Max retries exceeded",
            }

    async def _process_shop_billing_single(
        self, shop: Shop, period: BillingPeriod, dry_run: bool
    ) -> Dict[str, Any]:
        """Process billing for a single shop with fresh session - TRANSACTION SAFE"""
        try:
            # ✅ FIX: Use fresh session for each shop processing
            async with get_transaction_context() as session:
                billing_service = BillingServiceV2(session)
                billing_repository = BillingRepositoryV2(session)

                # Process billing with fresh session
                return await self._process_shop_billing_with_session(
                    shop, period, dry_run, billing_service, billing_repository
                )
        except Exception as e:
            logger.error(f"Error processing billing for shop {shop.id}: {e}")
            return {"success": False, "shop_id": shop.id, "error": str(e)}

    async def _process_shop_billing_with_session(
        self,
        shop: Shop,
        period: BillingPeriod,
        dry_run: bool,
        billing_service: BillingServiceV2,
        billing_repository: BillingRepositoryV2,
    ) -> Dict[str, Any]:
        """Process billing for a single shop with provided services - TRANSACTION SAFE"""
        try:
            # Get shop subscription
            shop_subscription = await billing_repository.get_shop_subscription(shop.id)
            if not shop_subscription:
                return {
                    "success": False,
                    "shop_id": shop.id,
                    "error": "No subscription found",
                }

            # Process billing based on subscription status
            if shop_subscription.status == SubscriptionStatus.TRIAL:
                # Handle trial billing
                return await self._handle_trial_billing(
                    shop,
                    shop_subscription,
                    period,
                    dry_run,
                    billing_service,
                    billing_repository,
                )
            elif shop_subscription.status == SubscriptionStatus.ACTIVE:
                # Handle active subscription billing
                return await self._handle_active_billing(
                    shop,
                    shop_subscription,
                    period,
                    dry_run,
                    billing_service,
                    billing_repository,
                )
            else:
                return {
                    "success": False,
                    "shop_id": shop.id,
                    "error": f"Invalid subscription status: {shop_subscription.status}",
                }

        except Exception as e:
            logger.error(f"Error processing billing for shop {shop.id}: {e}")
            return {"success": False, "shop_id": shop.id, "error": str(e)}

    async def _process_shop_billing(
        self, shop: Shop, period: BillingPeriod, dry_run: bool
    ) -> Dict[str, Any]:
        """Process billing for a single shop (legacy method for backward compatibility)"""
        try:
            return await self.process_shop_billing(shop.id, period, dry_run)
        except Exception as e:
            logger.error(f"Error processing billing for shop {shop.id}: {e}")
            return {"success": False, "shop_id": shop.id, "error": str(e)}

    async def _create_billing_invoice(
        self,
        session,
        shop: Shop,
        shop_subscription: ShopSubscription,
        billing_result: Dict[str, Any],
        period: BillingPeriod,
    ):
        """Create a billing invoice for the shop"""
        try:
            # Note: BillingInvoice model has been removed with the old system
            # Invoices are now handled by Shopify's billing system
            logger.info(
                f"Billing invoice creation skipped - using Shopify billing for shop {shop.id}"
            )
            return None

        except Exception as e:
            logger.error(f"Error creating billing invoice for shop {shop.id}: {e}")
            raise

    def _get_previous_month_period(self) -> BillingPeriod:
        """Get billing period for previous month"""
        now = now_utc()
        first_day_current_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        first_day_previous_month = last_day_previous_month.replace(day=1)

        return BillingPeriod(
            start_date=first_day_previous_month,
            end_date=last_day_previous_month,
            cycle="monthly",
        )

    async def get_billing_status(self) -> Dict[str, Any]:
        """Get current billing status and statistics."""
        try:
            async with get_transaction_context() as session:
                active_shops_count = (
                    await session.execute(
                        select(func.count(Shop.id)).where(Shop.is_active == True)
                    )
                ).scalar()

                shops_on_paid = (
                    await session.execute(
                        select(func.count(ShopSubscription.id)).where(
                            and_(
                                ShopSubscription.status == SubscriptionStatus.ACTIVE,
                                ShopSubscription.is_active == True,
                            )
                        )
                    )
                ).scalar()

                shops_on_trial = (
                    await session.execute(
                        select(func.count(ShopSubscription.id)).where(
                            and_(
                                ShopSubscription.status == SubscriptionStatus.TRIAL,
                                ShopSubscription.is_active == True,
                            )
                        )
                    )
                ).scalar()

                return {
                    "status": "healthy",
                    "active_shops": active_shops_count,
                    "shops_on_paid_subscription": shops_on_paid,
                    "shops_on_trial": shops_on_trial,
                    "last_updated": now_utc().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting billing status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_updated": now_utc().isoformat(),
            }

    async def _handle_trial_billing(
        self,
        shop: Shop,
        shop_subscription: ShopSubscription,
        period: BillingPeriod,
        dry_run: bool,
        billing_service: BillingServiceV2,
        billing_repository: BillingRepositoryV2,
    ) -> Dict[str, Any]:
        """Handle billing for trial shops - TRANSACTION SAFE"""
        try:
            # Trial shops don't get charged, just track progress
            logger.info(f"Trial shop {shop.id} - no billing charges")
            return {
                "success": True,
                "shop_id": shop.id,
                "status": "trial",
                "message": "Trial shop - no charges applied",
            }
        except Exception as e:
            logger.error(f"Error handling trial billing for shop {shop.id}: {e}")
            return {"success": False, "shop_id": shop.id, "error": str(e)}

    async def _handle_active_billing(
        self,
        shop: Shop,
        shop_subscription: ShopSubscription,
        period: BillingPeriod,
        dry_run: bool,
        billing_service: BillingServiceV2,
        billing_repository: BillingRepositoryV2,
    ) -> Dict[str, Any]:
        """Report current billing cycle usage for an active subscription shop."""
        try:
            billing_cycle = await billing_repository.get_current_billing_cycle(
                shop_subscription.id
            )
            if not billing_cycle:
                return {"success": False, "shop_id": shop.id, "error": "No active billing cycle found"}

            return {
                "success": True,
                "shop_id": shop.id,
                "usage_amount": float(billing_cycle.usage_amount),
                "cap_amount": float(billing_cycle.current_cap_amount),
                "usage_percentage": billing_cycle.usage_percentage,
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"Error handling active billing for shop {shop.id}: {e}")
            return {"success": False, "shop_id": shop.id, "error": str(e)}
