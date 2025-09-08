#!/usr/bin/env python3
"""
Customer Linking Scheduler Script

This script runs the customer linking scheduler to periodically backfill
customer IDs for anonymous events based on UserIdentityLink records.

Usage:
    python -m app.scripts.run_customer_linking_scheduler [--interval 30] [--once]
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.domains.customer_linking.scheduler import customer_linking_scheduler
from app.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Main function to run the customer linking scheduler"""
    parser = argparse.ArgumentParser(description="Run customer linking scheduler")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval between backfill jobs in minutes (default: 30)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run backfill job once and exit (default: run continuously)",
    )

    args = parser.parse_args()

    try:
        if args.once:
            logger.info("Running customer linking backfill job once")
            result = await customer_linking_scheduler.run_backfill_job()
            logger.info(f"Backfill job completed: {result}")
        else:
            logger.info(
                f"Starting periodic customer linking backfill (interval: {args.interval} minutes)"
            )
            await customer_linking_scheduler.run_periodic_backfill(args.interval)

    except KeyboardInterrupt:
        logger.info("Customer linking scheduler stopped by user")
    except Exception as e:
        logger.error(f"Customer linking scheduler failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
