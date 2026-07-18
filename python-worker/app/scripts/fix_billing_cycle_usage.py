"""
Script to fix billing cycle usage amounts by recalculating from RECORDED commissions.

This fixes cases where usage_amount was incorrectly counted (e.g., double-counting,
counting before Shopify recording, or including trial commissions).

Usage:
    # Dry run - show what would be fixed
    python -m app.scripts.fix_billing_cycle_usage --dry-run

    # Fix all active billing cycles
    python -m app.scripts.fix_billing_cycle_usage

    # Fix specific shop
    python -m app.scripts.fix_billing_cycle_usage --shop-id <shop_id>

    # Fix specific cycle
    python -m app.scripts.fix_billing_cycle_usage --cycle-id <cycle_id>

    # Only fix cycles where usage exceeds cap
    python -m app.scripts.fix_billing_cycle_usage --only-exceeding-cap
"""

import asyncio
import argparse
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os
from dotenv import load_dotenv

load_dotenv("../../.env.local")

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.core.database.session import get_transaction_context
from app.domains.billing.repositories.billing_repository_v2 import BillingRepositoryV2
from app.core.database.models.billing_cycle import BillingCycle
from app.core.database.models.enums import (
    BillingCycleStatus,
    CommissionStatus,
    BillingPhase,
)
from sqlalchemy import select, and_, func, update
from app.shared.helpers import now_utc
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Fix billing cycle usage amounts by recalculating from RECORDED commissions"
    )
    parser.add_argument(
        "--shop-id",
        help="Optional shop ID to fix cycles for",
    )
    parser.add_argument(
        "--cycle-id",
        help="Optional specific billing cycle ID to fix",
    )
    parser.add_argument(
        "--only-exceeding-cap",
        action="store_true",
        help="Only fix cycles where usage exceeds cap",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )

    args = parser.parse_args()

    result = asyncio.run(
        fix_billing_cycle_usage(
            shop_id=args.shop_id,
            cycle_id=args.cycle_id,
            only_exceeding_cap=args.only_exceeding_cap,
            dry_run=args.dry_run,
        )
    )

    if result.get("success"):
        print(f"\n✅ Success!")
        print(f"   Cycles checked: {result['cycles_checked']}")
        print(f"   Cycles fixed: {result['cycles_fixed']}")
        print(f"   Total usage corrected: ${result['total_usage_corrected']:.2f}")

        if result.get("fixes_applied"):
            print(f"\n📋 Detailed fixes:")
            for fix in result["fixes_applied"]:
                print(f"   Cycle {fix['cycle_id'][:8]}...:")
                print(
                    f"      Old usage: ${fix['old_usage']:.2f} → New usage: ${fix['new_usage']:.2f}"
                )
                print(f"      Difference: ${fix['difference']:+.2f}")
                print(f"      Cap: ${fix['current_cap']:.2f}")
                print(
                    f"      Remaining cap: ${fix['remaining_cap_before']:.2f} → ${fix['remaining_cap_after']:.2f}"
                )
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
        exit(1)


if __name__ == "__main__":
    main()
