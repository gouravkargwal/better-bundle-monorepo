#!/usr/bin/env python3
"""
Shopify Usage Records Fetcher

This script fetches usage records from Shopify for a specific shop.
It can be used to:
1. Fetch all usage records for a shop
2. Fetch usage records for a specific subscription
3. Fetch usage records within a date range
4. Compare with local database records

Usage:
    python fetch_shopify_usage_records.py --shop-id <shop_id>
    python fetch_shopify_usage_records.py --shop-id <shop_id> --subscription-id <subscription_id>
    python fetch_shopify_usage_records.py --shop-id <shop_id> --since 2024-01-01 --until 2024-12-31
    python fetch_shopify_usage_records.py --shop-id <shop_id> --compare-db
"""

import asyncio
import argparse
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the path to import app modules
import sys
import os

# Get the parent directory (python-worker)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, parent_dir)

from app.core.database.session import get_session_context
from app.core.database.models import Shop, BillingPlan, CommissionRecord
from app.domains.billing.repositories.billing_repository import BillingRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Shopify usage record data"""

    id: str
    subscription_line_item_id: str
    description: str
    price: Dict[str, Any]
    created_at: str
    subscription_id: Optional[str] = None


@dataclass
class UsageRecordSummary:
    """Summary of usage records"""

    total_records: int
    total_amount: Decimal
    currency: str
    date_range: str
    records: List[UsageRecord]


class ShopifyUsageFetcher:
    """Service for fetching usage records from Shopify"""

    def __init__(self):
        self.base_url = "https://{shop_domain}/admin/api/2024-01/graphql.json"

    async def fetch_usage_records(
        self,
        shop_domain: str,
        access_token: str,
        subscription_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[UsageRecord]:
        """
        Fetch usage records from Shopify

        Args:
            shop_domain: Shop domain
            access_token: Shop access token
            subscription_id: Optional subscription ID to filter by
            since: Optional start date
            until: Optional end date
            limit: Maximum number of records to fetch

        Returns:
            List of usage records
        """
        try:
            # GraphQL query for fetching subscription with usage balance
            query = """
            query getSubscription($id: ID!) {
                node(id: $id) {
                    ... on AppSubscription {
                        id
                        name
                        status
                        lineItems {
                            id
                            plan {
                                pricingDetails {
                                    __typename
                                    ... on AppUsagePricing {
                                        terms
                                        cappedAmount {
                                            amount
                                            currencyCode
                                        }
                                        balanceUsed {
                                            amount
                                            currencyCode
                                        }
                                    }
                                }
                            }
                        }
                        createdAt
                    }
                }
            }
            """

            if not subscription_id:
                logger.error("Subscription ID is required to fetch usage information")
                return []

            variables = {"id": subscription_id}

            response = await self._make_graphql_request(
                shop_domain, access_token, query, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors: {response['errors']}")
                return []

            data = response.get("data", {}).get("node")
            if not data:
                logger.error("No subscription data returned")
                return []

            # Extract usage information from subscription
            all_records = []

            for line_item in data.get("lineItems", []):
                plan = line_item.get("plan", {})
                pricing_details = plan.get("pricingDetails", {})

                if pricing_details.get("__typename") == "AppUsagePricing":
                    balance_used = pricing_details.get("balanceUsed", {})
                    capped_amount = pricing_details.get("cappedAmount", {})

                    # Create a summary record showing current usage
                    record = UsageRecord(
                        id=f"usage_summary_{line_item['id']}",
                        subscription_line_item_id=line_item["id"],
                        subscription_id=data["id"],
                        description=f"Current usage balance for {data.get('name', 'Subscription')}",
                        price=balance_used,
                        created_at=data.get("createdAt", ""),
                    )

                    all_records.append(record)

            logger.info(
                f"Fetched subscription usage info: {len(all_records)} line items"
            )
            return all_records

        except Exception as e:
            logger.error(f"Error fetching usage records: {e}")
            return []

    async def _make_graphql_request(
        self, shop_domain: str, access_token: str, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a GraphQL request to Shopify"""
        url = self.base_url.format(shop_domain=shop_domain)

        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        payload = {"query": query, "variables": variables}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    def summarize_records(self, records: List[UsageRecord]) -> UsageRecordSummary:
        """Create a summary of usage records"""
        if not records:
            return UsageRecordSummary(
                total_records=0,
                total_amount=Decimal("0"),
                currency="USD",
                date_range="No records",
                records=[],
            )

        # Calculate total amount
        total_amount = Decimal("0")
        currency = "USD"

        for record in records:
            amount = Decimal(str(record.price.get("amount", 0)))
            total_amount += amount
            currency = record.price.get("currencyCode", "USD")

        # Get date range
        dates = [
            datetime.fromisoformat(r.created_at.replace("Z", "+00:00")) for r in records
        ]
        min_date = min(dates).strftime("%Y-%m-%d")
        max_date = max(dates).strftime("%Y-%m-%d")
        date_range = f"{min_date} to {max_date}"

        return UsageRecordSummary(
            total_records=len(records),
            total_amount=total_amount,
            currency=currency,
            date_range=date_range,
            records=records,
        )


class DatabaseComparator:
    """Compare Shopify usage records with local database"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_local_commission_records(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get commission records from local database"""
        try:
            # First, let's get ALL commission records for this shop to see what we have
            stmt = (
                select(CommissionRecord)
                .where(CommissionRecord.shop_id == shop_id)
                .order_by(CommissionRecord.created_at.desc())
            )

            result = await self.session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "id": record.id,
                    "shopify_usage_record_id": record.shopify_usage_record_id,
                    "commission_charged": float(record.commission_earned or 0),
                    "status": record.status.value,
                    "billing_phase": record.billing_phase.value,
                    "created_at": record.created_at.isoformat(),
                    "shopify_recorded_at": (
                        record.shopify_recorded_at.isoformat()
                        if record.shopify_recorded_at
                        else None
                    ),
                }
                for record in records
            ]
        except Exception as e:
            logger.error(f"Error fetching local commission records: {e}")
            return []

    def compare_records(
        self, shopify_records: List[UsageRecord], local_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare Shopify records with local database records"""

        # For comparison, we'll compare amounts rather than IDs since Shopify doesn't provide
        # individual usage record IDs in the subscription query
        shopify_total = sum(
            Decimal(str(record.price.get("amount", 0))) for record in shopify_records
        )

        # Calculate totals for different phases
        trial_total = sum(
            Decimal(str(record["commission_charged"]))
            for record in local_records
            if record["billing_phase"] == "TRIAL"
        )
        paid_total = sum(
            Decimal(str(record["commission_charged"]))
            for record in local_records
            if record["billing_phase"] == "PAID"
        )
        recorded_total = sum(
            Decimal(str(record["commission_charged"]))
            for record in local_records
            if record["shopify_usage_record_id"] is not None
        )

        local_total = trial_total + paid_total

        # Calculate difference
        difference = float(shopify_total - recorded_total)

        # Check if amounts are close (within 0.01 to account for rounding)
        amounts_match = abs(difference) < 0.01

        return {
            "summary": {
                "shopify_records": len(shopify_records),
                "local_records": len(local_records),
                "trial_records": len(
                    [r for r in local_records if r["billing_phase"] == "TRIAL"]
                ),
                "paid_records": len(
                    [r for r in local_records if r["billing_phase"] == "PAID"]
                ),
                "recorded_records": len(
                    [
                        r
                        for r in local_records
                        if r["shopify_usage_record_id"] is not None
                    ]
                ),
                "matched_records": 1 if amounts_match else 0,
                "shopify_only": 0 if amounts_match else 1,
                "local_only": 0 if amounts_match else 1,
                "shopify_total": float(shopify_total),
                "local_total": float(local_total),
                "trial_total": float(trial_total),
                "paid_total": float(paid_total),
                "recorded_total": float(recorded_total),
                "difference": difference,
                "amounts_match": amounts_match,
            },
            "shopify_only_ids": [] if amounts_match else ["usage_balance"],
            "local_only_ids": [] if amounts_match else ["commission_records"],
            "matched_ids": ["usage_balance"] if amounts_match else [],
            "local_records_detail": local_records,
        }


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Fetch Shopify usage records")
    parser.add_argument("--shop-id", required=True, help="Shop ID")
    parser.add_argument(
        "--subscription-id", help="Optional subscription ID to filter by"
    )
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--limit", type=int, default=50, help="Maximum records to fetch"
    )
    parser.add_argument(
        "--compare-db", action="store_true", help="Compare with local database"
    )
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse dates
    since = None
    until = None
    if args.since:
        since = datetime.fromisoformat(args.since)
    if args.until:
        until = datetime.fromisoformat(args.until)

    async with get_session_context() as session:
        # Get shop information
        shop_stmt = select(Shop).where(Shop.id == args.shop_id)
        shop_result = await session.execute(shop_stmt)
        shop = shop_result.scalar_one_or_none()

        if not shop:
            logger.error(f"Shop not found: {args.shop_id}")
            return

        logger.info(f"Fetching usage records for shop: {shop.shop_domain}")

        # Get subscription ID from billing plan if not provided
        subscription_id = args.subscription_id
        if not subscription_id:
            billing_plan_stmt = select(BillingPlan).where(
                and_(
                    BillingPlan.shop_id == args.shop_id,
                    BillingPlan.subscription_id.isnot(None),
                )
            )
            billing_plan_result = await session.execute(billing_plan_stmt)
            billing_plan = billing_plan_result.scalar_one_or_none()

            if billing_plan and billing_plan.subscription_id:
                subscription_id = billing_plan.subscription_id
                logger.info(f"Found subscription ID: {subscription_id}")
            else:
                logger.error("No subscription found for this shop")
                return

        # Fetch usage records from Shopify
        fetcher = ShopifyUsageFetcher()
        records = await fetcher.fetch_usage_records(
            shop_domain=shop.shop_domain,
            access_token=shop.access_token,
            subscription_id=subscription_id,
            since=since,
            until=until,
            limit=args.limit,
        )

        # Create summary
        summary = fetcher.summarize_records(records)

        # Print summary
        print(f"\n📊 Usage Records Summary for {shop.shop_domain}")
        print(f"Total Records: {summary.total_records}")
        print(f"Total Amount: {summary.currency} {summary.total_amount}")
        print(f"Date Range: {summary.date_range}")

        if args.verbose:
            print(f"\n📋 Detailed Records:")
            for record in records:
                print(f"  ID: {record.id}")
                print(
                    f"  Amount: {record.price.get('currencyCode', 'USD')} {record.price.get('amount', 0)}"
                )
                print(f"  Description: {record.description}")
                print(f"  Created: {record.created_at}")
                print(f"  Subscription: {record.subscription_id}")
                print()

        # Compare with database if requested
        if args.compare_db:
            logger.info("Comparing with local database...")
            comparator = DatabaseComparator(session)
            local_records = await comparator.get_local_commission_records(args.shop_id)
            comparison = comparator.compare_records(records, local_records)

            print(f"\n🔍 Database Comparison:")
            print(f"Shopify Records: {comparison['summary']['shopify_records']}")
            print(
                f"Local Records: {comparison['summary']['local_records']} (Trial: {comparison['summary']['trial_records']}, Paid: {comparison['summary']['paid_records']})"
            )
            print(f"Recorded with Shopify: {comparison['summary']['recorded_records']}")
            print(f"Matched: {comparison['summary']['matched_records']}")
            print(f"Shopify Only: {comparison['summary']['shopify_only']}")
            print(f"Local Only: {comparison['summary']['local_only']}")
            print(f"Shopify Total: {comparison['summary']['shopify_total']}")
            print(
                f"Local Total: {comparison['summary']['local_total']} (Trial: {comparison['summary']['trial_total']}, Paid: {comparison['summary']['paid_total']})"
            )
            print(f"Recorded Total: {comparison['summary']['recorded_total']}")
            print(f"Difference: {comparison['summary']['difference']}")

            if comparison["shopify_only_ids"]:
                print(
                    f"\n⚠️ Records in Shopify but not in local DB: {comparison['shopify_only_ids']}"
                )
            if comparison["local_only_ids"]:
                print(
                    f"\n⚠️ Records in local DB but not in Shopify: {comparison['local_only_ids']}"
                )

            # Show detailed local records
            if comparison["local_records_detail"]:
                print(f"\n📋 Local Commission Records:")
                for record in comparison["local_records_detail"]:
                    print(f"  ID: {record['id'][:8]}...")
                    print(f"  Amount: {record['commission_charged']}")
                    print(f"  Status: {record['status']}")
                    print(f"  Phase: {record['billing_phase']}")
                    print(
                        f"  Shopify ID: {record['shopify_usage_record_id'] or 'None'}"
                    )
                    print()

        # Save to file if requested
        if args.output:
            output_data = {
                "shop_id": args.shop_id,
                "shop_domain": shop.shop_domain,
                "summary": asdict(summary),
                "records": [asdict(record) for record in records],
            }

            if args.compare_db:
                output_data["comparison"] = comparison

            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)

            logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
