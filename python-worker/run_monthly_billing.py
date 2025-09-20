#!/usr/bin/env python3
"""
Monthly Billing Runner for GitHub Actions

This script runs the monthly billing job and can be executed
independently of the FastAPI application.
"""

import asyncio
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_monthly_billing():
    """Run the monthly billing job"""
    try:
        logger.info("🚀 Starting monthly billing job...")

        # Import here to avoid circular imports
        from app.domains.billing.jobs.monthly_billing_job import run_monthly_billing_job

        # Run the billing job
        result = await run_monthly_billing_job()

        logger.info(f"✅ Monthly billing completed successfully")
        logger.info(f"📊 Result: {result}")

        return result

    except Exception as e:
        logger.error(f"❌ Monthly billing failed: {e}")
        raise


async def main():
    """Main entry point"""
    try:
        start_time = datetime.utcnow()
        logger.info(f"🕐 Monthly billing job started at {start_time}")

        result = await run_monthly_billing()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"⏱️ Job completed in {duration:.2f} seconds")
        logger.info(f"📈 Processed {result.get('processed_shops', 0)} shops")
        logger.info(f"💰 Total fees: ${result.get('total_fees', 0)}")

        return 0

    except Exception as e:
        logger.error(f"💥 Monthly billing job failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
