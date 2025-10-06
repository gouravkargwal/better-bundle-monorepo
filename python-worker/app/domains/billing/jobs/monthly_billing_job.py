"""
Monthly Billing Job

This job runs monthly to calculate and process billing for all shops.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

from prisma import Prisma

from ..services.billing_service import BillingService
from ..repositories.billing_repository import BillingRepository, BillingPeriod

logger = logging.getLogger(__name__)


class MonthlyBillingJob:
    """
    Monthly billing job that processes billing for all shops.
    """

    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.billing_service = BillingService(prisma)
        self.billing_repository = BillingRepository(prisma)

    async def run_monthly_billing(self) -> Dict[str, Any]:
        """
        Run monthly billing for all shops.

        Returns:
            Job execution summary
        """
        job_start_time = datetime.utcnow()
        logger.info(f"Starting monthly billing job at {job_start_time}")

        try:
            # Get all shops for billing
            shop_ids = await self.billing_repository.get_shops_for_billing()

            if not shop_ids:
                logger.info("No shops found for billing processing")
                return {
                    "status": "completed",
                    "message": "No shops found for billing",
                    "processed_shops": 0,
                    "total_fees": 0,
                    "start_time": job_start_time.isoformat(),
                    "end_time": datetime.utcnow().isoformat(),
                    "duration_seconds": 0,
                }

            logger.info(f"Found {len(shop_ids)} shops for billing processing")

            # Process billing for all shops with Shopify integration
            billing_result = (
                await self.billing_service.process_all_shop_billing_with_shopify()
            )

            # Calculate job statistics
            job_end_time = datetime.utcnow()
            duration = (job_end_time - job_start_time).total_seconds()

            result = {
                "status": "completed",
                "message": "Monthly billing job completed successfully",
                "processed_shops": billing_result.get("processed_shops", 0),
                "total_shops": billing_result.get("total_shops", 0),
                "total_fees": billing_result.get("total_fees", 0),
                "errors": billing_result.get("errors", []),
                "start_time": job_start_time.isoformat(),
                "end_time": job_end_time.isoformat(),
                "duration_seconds": duration,
            }

            logger.info(
                f"Monthly billing job completed: {result['processed_shops']}/{result['total_shops']} shops processed, "
                f"total fees: ${result['total_fees']}, duration: {duration:.2f}s"
            )

            return result

        except Exception as e:
            job_end_time = datetime.utcnow()
            duration = (job_end_time - job_start_time).total_seconds()

            error_msg = f"Monthly billing job failed: {e}"
            logger.error(error_msg)

            return {
                "status": "failed",
                "message": error_msg,
                "processed_shops": 0,
                "total_fees": 0,
                "errors": [error_msg],
                "start_time": job_start_time.isoformat(),
                "end_time": job_end_time.isoformat(),
                "duration_seconds": duration,
            }

    async def run_shop_billing(self, shop_id: str) -> Dict[str, Any]:
        """
        Run billing for a specific shop.

        Args:
            shop_id: Shop ID to process

        Returns:
            Shop billing result
        """
        logger.info(f"Running billing for shop {shop_id}")

        try:
            # Calculate monthly billing
            billing_result = await self.billing_service.calculate_monthly_billing(
                shop_id
            )

            if billing_result.get("error"):
                return {
                    "status": "failed",
                    "shop_id": shop_id,
                    "message": billing_result["error"],
                    "fee": 0,
                }

            return {
                "status": "completed",
                "shop_id": shop_id,
                "message": "Billing calculated successfully",
                "fee": billing_result.get("calculation", {}).get("final_fee", 0),
                "revenue": billing_result.get("metrics", {}).get(
                    "attributed_revenue", 0
                ),
                "period": billing_result.get("period", {}),
                "calculated_at": billing_result.get("calculated_at"),
            }

        except Exception as e:
            error_msg = f"Error processing billing for shop {shop_id}: {e}"
            logger.error(error_msg)

            return {
                "status": "failed",
                "shop_id": shop_id,
                "message": error_msg,
                "fee": 0,
            }

    async def create_billing_plans_for_new_shops(self) -> Dict[str, Any]:
        """
        Create billing plans for shops that don't have them.

        Returns:
            Creation summary
        """
        logger.info("Creating billing plans for new shops")

        try:
            # Get all shops from the database
            shops = await self.prisma.shop.find_many(
                select={"id": True, "domain": True}
            )

            created_plans = 0
            errors = []

            for shop in shops:
                try:
                    # Check if shop already has a billing plan
                    existing_plan = await self.billing_repository.get_billing_plan(
                        shop.id
                    )

                    if not existing_plan:
                        # Create default billing plan
                        await self.billing_service.create_default_billing_plan(
                            shop.id, shop.domain
                        )
                        created_plans += 1
                        logger.info(f"Created billing plan for shop {shop.id}")

                except Exception as e:
                    error_msg = f"Error creating billing plan for shop {shop.id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                "status": "completed",
                "message": f"Created {created_plans} billing plans",
                "created_plans": created_plans,
                "total_shops": len(shops),
                "errors": errors,
            }

        except Exception as e:
            error_msg = f"Error creating billing plans: {e}"
            logger.error(error_msg)

            return {
                "status": "failed",
                "message": error_msg,
                "created_plans": 0,
                "total_shops": 0,
                "errors": [error_msg],
            }

    async def cleanup_old_billing_data(
        self, months_to_keep: int = 24
    ) -> Dict[str, Any]:
        """
        Clean up old billing data to keep database size manageable.

        Args:
            months_to_keep: Number of months of data to keep

        Returns:
            Cleanup summary
        """
        logger.info(f"Cleaning up billing data older than {months_to_keep} months")

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=months_to_keep * 30)

            # Clean up old billing metrics (keep invoices for audit)
            deleted_metrics = await self.prisma.billingmetrics.delete_many(
                where={"calculatedAt": {"lt": cutoff_date}}
            )

            return {
                "status": "completed",
                "message": f"Cleaned up billing data older than {months_to_keep} months",
                "deleted_metrics": deleted_metrics,
                "cutoff_date": cutoff_date.isoformat(),
            }

        except Exception as e:
            error_msg = f"Error cleaning up billing data: {e}"
            logger.error(error_msg)

            return {
                "status": "failed",
                "message": error_msg,
                "deleted_events": 0,
                "deleted_metrics": 0,
            }

    async def run_maintenance_tasks(self) -> Dict[str, Any]:
        """
        Run maintenance tasks for the billing system.

        Returns:
            Maintenance summary
        """
        logger.info("Running billing system maintenance tasks")

        try:
            results = {}

            # Create billing plans for new shops
            results["billing_plans"] = await self.create_billing_plans_for_new_shops()

            # Clean up old data
            results["cleanup"] = await self.cleanup_old_billing_data()

            return {
                "status": "completed",
                "message": "Maintenance tasks completed",
                "results": results,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            error_msg = f"Error running maintenance tasks: {e}"
            logger.error(error_msg)

            return {
                "status": "failed",
                "message": error_msg,
                "results": {},
                "completed_at": datetime.utcnow().isoformat(),
            }


# Standalone functions for easy scheduling
async def run_monthly_billing_job() -> Dict[str, Any]:
    """Run the monthly billing job."""
    prisma = Prisma()
    await prisma.connect()

    try:
        job = MonthlyBillingJob(prisma)
        result = await job.run_monthly_billing()
        return result
    finally:
        await prisma.disconnect()


async def run_billing_maintenance() -> Dict[str, Any]:
    """Run billing maintenance tasks."""
    prisma = Prisma()
    await prisma.connect()

    try:
        job = MonthlyBillingJob(prisma)
        result = await job.run_maintenance_tasks()
        return result
    finally:
        await prisma.disconnect()


async def run_shop_billing_job(shop_id: str) -> Dict[str, Any]:
    """Run billing for a specific shop."""
    prisma = Prisma()
    await prisma.connect()

    try:
        job = MonthlyBillingJob(prisma)
        result = await job.run_shop_billing(shop_id)
        return result
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    # For testing purposes
    async def main():
        result = await run_monthly_billing_job()
        print(f"Billing job result: {result}")

    asyncio.run(main())
