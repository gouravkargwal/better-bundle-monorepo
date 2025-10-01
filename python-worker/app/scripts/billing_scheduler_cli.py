#!/usr/bin/env python3
"""
Billing Scheduler CLI

Command-line interface for running the billing scheduler service.
This can be used for manual billing runs, testing, and debugging.
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import List, Optional

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.billing_scheduler_service import BillingSchedulerService
from app.domains.billing.repositories.billing_repository import BillingPeriod
from app.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Billing Scheduler CLI")

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process billing command
    process_parser = subparsers.add_parser("process", help="Process billing for shops")
    process_parser.add_argument(
        "--shop-ids",
        nargs="+",
        help="List of shop IDs to process (default: all active shops)",
    )
    process_parser.add_argument(
        "--dry-run", action="store_true", help="Calculate but don't create invoices"
    )
    process_parser.add_argument(
        "--period-start", help="Billing period start date (YYYY-MM-DD)"
    )
    process_parser.add_argument(
        "--period-end", help="Billing period end date (YYYY-MM-DD)"
    )
    process_parser.add_argument(
        "--previous-month",
        action="store_true",
        help="Use previous month as billing period",
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Get billing status")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test billing for a specific shop")
    test_parser.add_argument("shop_id", help="Shop ID to test")
    test_parser.add_argument(
        "--dry-run", action="store_true", help="Calculate but don't create invoices"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "process":
            await process_billing(args)
        elif args.command == "status":
            await get_status()
        elif args.command == "test":
            await test_shop_billing(args)
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error running billing scheduler CLI: {e}")
        sys.exit(1)


async def process_billing(args):
    """Process billing for shops"""
    try:
        logger.info("Starting billing scheduler CLI")

        # Initialize scheduler service
        scheduler = BillingSchedulerService()
        await scheduler.initialize()

        # Parse shop IDs
        shop_ids = args.shop_ids if args.shop_ids else None

        # Parse billing period
        period = None
        if args.period_start and args.period_end:
            try:
                period_start = datetime.fromisoformat(args.period_start)
                period_end = datetime.fromisoformat(args.period_end)
                period = BillingPeriod(
                    start_date=period_start, end_date=period_end, cycle="monthly"
                )
            except ValueError as e:
                logger.error(f"Invalid date format: {e}")
                sys.exit(1)
        elif args.previous_month:
            # Use previous month
            now = datetime.utcnow()
            first_day_current_month = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            last_day_previous_month = first_day_current_month - timedelta(days=1)
            first_day_previous_month = last_day_previous_month.replace(day=1)

            period = BillingPeriod(
                start_date=first_day_previous_month,
                end_date=last_day_previous_month,
                cycle="monthly",
            )

        # Process billing
        result = await scheduler.process_monthly_billing(
            shop_ids=shop_ids, period=period, dry_run=args.dry_run
        )

        # Print results
        print_billing_results(result)

        # Exit with error code if there were failures
        if result.get("failed_shops", 0) > 0:
            logger.warning(
                f"{result.get('failed_shops', 0)} shops failed billing processing"
            )
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error processing billing: {e}")
        sys.exit(1)


async def get_status():
    """Get billing status"""
    try:
        logger.info("Getting billing status")

        # Initialize scheduler service
        scheduler = BillingSchedulerService()
        await scheduler.initialize()

        # Get status
        status = await scheduler.get_billing_status()

        # Print status
        print("Billing Status:")
        print(f"  Status: {status.get('status', 'unknown')}")
        print(f"  Active shops: {status.get('active_shops', 0)}")
        print(
            f"  Shops with billing plans: {status.get('shops_with_billing_plans', 0)}"
        )
        print(f"  Pending invoices: {status.get('pending_invoices', 0)}")
        print(f"  Last updated: {status.get('last_updated', 'unknown')}")

    except Exception as e:
        logger.error(f"Error getting billing status: {e}")
        sys.exit(1)


async def test_shop_billing(args):
    """Test billing for a specific shop"""
    try:
        logger.info(f"Testing billing for shop {args.shop_id}")

        # Initialize scheduler service
        scheduler = BillingSchedulerService()
        await scheduler.initialize()

        # Process billing for the shop
        result = await scheduler.process_shop_billing(
            shop_id=args.shop_id,
            period=None,  # Use previous month
            dry_run=args.dry_run,
        )

        # Print results
        if result.get("success", False):
            print(f"✅ Billing test successful for shop {args.shop_id}")
            print(f"  Shop domain: {result.get('shop_domain', 'unknown')}")
            print(f"  Attributed revenue: ${result.get('attributed_revenue', 0.0):.2f}")
            print(f"  Calculated fee: ${result.get('calculated_fee', 0.0):.2f}")
            print(f"  Currency: {result.get('currency', 'USD')}")
            print(f"  Invoice ID: {result.get('invoice_id', 'N/A')}")
            print(f"  Dry run: {result.get('dry_run', False)}")
        else:
            print(f"❌ Billing test failed for shop {args.shop_id}")
            print(f"  Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error testing shop billing: {e}")
        sys.exit(1)


def print_billing_results(result: dict):
    """Print billing results in a formatted way"""
    print("\n" + "=" * 60)
    print("BILLING SCHEDULER RESULTS")
    print("=" * 60)
    print(f"Status: {result.get('status', 'unknown')}")
    print(
        f"Period: {result.get('period', {}).get('start_date', 'unknown')} to {result.get('period', {}).get('end_date', 'unknown')}"
    )
    print(f"Processed shops: {result.get('processed_shops', 0)}")
    print(f"Successful: {result.get('successful_shops', 0)}")
    print(f"Failed: {result.get('failed_shops', 0)}")
    print(f"Total revenue: ${result.get('total_revenue', 0.0):.2f}")
    print(f"Total fees: ${result.get('total_fees', 0.0):.2f}")
    print(f"Dry run: {result.get('dry_run', False)}")
    print(f"Started at: {result.get('started_at', 'unknown')}")
    print(f"Completed at: {result.get('completed_at', 'unknown')}")

    # Print errors if any
    if result.get("errors"):
        print(f"\nErrors ({len(result['errors'])}):")
        for i, error in enumerate(result["errors"][:10], 1):  # Show first 10 errors
            print(
                f"  {i}. Shop {error.get('shop_id', 'unknown')}: {error.get('error', 'Unknown error')}"
            )
        if len(result["errors"]) > 10:
            print(f"  ... and {len(result['errors']) - 10} more errors")

    # Print shop results summary
    if result.get("shop_results"):
        print(f"\nShop Results Summary:")
        successful_shops = [
            r for r in result["shop_results"] if r.get("success", False)
        ]
        failed_shops = [
            r for r in result["shop_results"] if not r.get("success", False)
        ]

        if successful_shops:
            print(f"  Successful shops ({len(successful_shops)}):")
            for shop_result in successful_shops[:5]:  # Show first 5
                print(
                    f"    - {shop_result.get('shop_domain', 'unknown')} (${shop_result.get('calculated_fee', 0.0):.2f})"
                )
            if len(successful_shops) > 5:
                print(f"    ... and {len(successful_shops) - 5} more")

        if failed_shops:
            print(f"  Failed shops ({len(failed_shops)}):")
            for shop_result in failed_shops[:5]:  # Show first 5
                print(
                    f"    - {shop_result.get('shop_id', 'unknown')}: {shop_result.get('error', 'Unknown error')}"
                )
            if len(failed_shops) > 5:
                print(f"    ... and {len(failed_shops) - 5} more")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
