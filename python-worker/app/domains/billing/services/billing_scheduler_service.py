"""
Enhanced Billing Scheduler Service with Parallel Processing

This service handles scheduled billing calculations with improved concurrency,
parallel processing, and robust error handling for GitHub Actions cron jobs.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from app.shared.helpers import now_utc
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.core.database.session import get_transaction_context
from app.core.database.models import Shop, BillingPlan, BillingInvoice
from app.core.logging import get_logger
from app.domains.billing.services.billing_service import BillingService
from app.domains.billing.repositories.billing_repository import (
    BillingRepository,
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
        """Initialize the billing service and repository"""
        try:
            # Initialize billing service with SQLAlchemy session
            async with get_transaction_context() as session:
                self.billing_service = BillingService(session)
                self.billing_repository = BillingRepository(session)

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
        """
        Process billing for a specific shop.

        Args:
            shop_id: Shop ID to process
            period: Billing period (defaults to previous month)
            dry_run: If True, calculate but don't create invoices

        Returns:
            Shop billing result
        """
        try:
            logger.info(f"Processing billing for shop {shop_id} - dry_run={dry_run}")

            # Initialize if not already done
            if not self.billing_service:
                await self.initialize()

            # Use previous month if no period specified
            if not period:
                period = self._get_previous_month_period()

            async with get_transaction_context() as session:
                # Get shop details
                shop_query = select(Shop).where(Shop.id == shop_id)
                shop_result = await session.execute(shop_query)
                shop = shop_result.scalar_one_or_none()

                if not shop:
                    return {
                        "success": False,
                        "shop_id": shop_id,
                        "error": "Shop not found",
                    }

                # Check if shop is active
                if not shop.is_active:
                    return {
                        "success": False,
                        "shop_id": shop_id,
                        "error": "Shop is not active",
                    }

                # Get billing plan
                billing_plan_query = select(BillingPlan).where(
                    and_(BillingPlan.shop_id == shop_id, BillingPlan.status == "ACTIVE")
                )
                billing_plan_result = await session.execute(billing_plan_query)
                billing_plan = billing_plan_result.scalar_one_or_none()

                if not billing_plan:
                    return {
                        "success": False,
                        "shop_id": shop_id,
                        "error": "No active billing plan found",
                    }

                # Calculate billing
                billing_service = BillingService(session)
                billing_result = await billing_service.calculate_monthly_billing(
                    shop_id, period
                )

                if not billing_result.get("success", False):
                    return {
                        "success": False,
                        "shop_id": shop_id,
                        "error": billing_result.get(
                            "error", "Billing calculation failed"
                        ),
                    }

                # Create invoice if not dry run
                if not dry_run and billing_result.get("final_fee", 0) > 0:
                    invoice = await self._create_billing_invoice(
                        session, shop, billing_plan, billing_result, period
                    )
                    billing_result["invoice_id"] = invoice.id

                return {
                    "success": True,
                    "shop_id": shop_id,
                    "shop_domain": shop.shop_domain,
                    "attributed_revenue": billing_result.get("attributed_revenue", 0.0),
                    "calculated_fee": billing_result.get("final_fee", 0.0),
                    "currency": billing_result.get("currency", "USD"),
                    "invoice_id": billing_result.get("invoice_id"),
                    "dry_run": dry_run,
                }

        except Exception as e:
            logger.error(f"Error processing billing for shop {shop_id}: {e}")
            return {"success": False, "shop_id": shop_id, "error": str(e)}

    async def _get_shops_to_process(
        self, shop_ids: Optional[List[str]] = None
    ) -> List[Shop]:
        """Get list of shops to process for billing"""
        async with get_transaction_context() as session:
            if shop_ids:
                # Process specific shops
                query = select(Shop).where(
                    and_(Shop.id.in_(shop_ids), Shop.is_active == True)
                )
            else:
                # Process all active shops with billing plans
                query = select(Shop).where(
                    and_(
                        Shop.is_active == True,
                        Shop.billing_plans.any(BillingPlan.status == "ACTIVE"),
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
        """Process billing for a single shop (internal method)"""
        try:
            return await self.process_shop_billing(shop.id, period, dry_run)
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
        billing_plan: BillingPlan,
        billing_result: Dict[str, Any],
        period: BillingPeriod,
    ) -> BillingInvoice:
        """Create a billing invoice for the shop"""
        try:
            invoice = BillingInvoice(
                shop_id=shop.id,
                plan_id=billing_plan.id,
                amount=float(billing_result.get("final_fee", 0.0)),
                currency_code=billing_result.get("currency", "USD"),
                status="PENDING",
                due_date=now_utc() + timedelta(days=30),
                period_start=period.start_date,
                period_end=period.end_date,
                metadata={
                    "attributed_revenue": billing_result.get("attributed_revenue", 0.0),
                    "calculation_breakdown": billing_result.get("breakdown", {}),
                    "created_by": "billing_scheduler",
                },
            )

            session.add(invoice)
            await session.flush()

            logger.info(f"Created billing invoice {invoice.id} for shop {shop.id}")
            return invoice

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
        """Get current billing status and statistics"""
        try:
            async with get_transaction_context() as session:
                # Get active shops count
                active_shops_query = select(func.count(Shop.id)).where(
                    Shop.is_active == True
                )
                active_shops_result = await session.execute(active_shops_query)
                active_shops_count = active_shops_result.scalar()

                # Get shops with billing plans
                shops_with_plans_query = select(func.count(Shop.id)).where(
                    and_(
                        Shop.is_active == True,
                        Shop.billing_plans.any(BillingPlan.status == "ACTIVE"),
                    )
                )
                shops_with_plans_result = await session.execute(shops_with_plans_query)
                shops_with_plans_count = shops_with_plans_result.scalar()

                # Get pending invoices
                pending_invoices_query = select(func.count(BillingInvoice.id)).where(
                    BillingInvoice.status == "PENDING"
                )
                pending_invoices_result = await session.execute(pending_invoices_query)
                pending_invoices_count = pending_invoices_result.scalar()

                return {
                    "status": "healthy",
                    "active_shops": active_shops_count,
                    "shops_with_billing_plans": shops_with_plans_count,
                    "pending_invoices": pending_invoices_count,
                    "last_updated": now_utc().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting billing status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_updated": now_utc().isoformat(),
            }
