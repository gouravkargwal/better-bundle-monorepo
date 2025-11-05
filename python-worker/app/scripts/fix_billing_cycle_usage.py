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
from app.core.database.models.commission import CommissionRecord
from app.core.database.models.enums import (
    BillingCycleStatus,
    CommissionStatus,
    BillingPhase,
)
from sqlalchemy import select, and_, func, update
from app.shared.helpers import now_utc
from app.core.logging import get_logger

logger = get_logger(__name__)


async def calculate_correct_usage(session, cycle_id: str) -> Decimal:
    """
    Calculate correct usage amount from RECORDED commissions only.

    This ensures:
    - Only PAID phase commissions count
    - Only RECORDED commissions count (successfully charged to Shopify)
    - Only commission_charged (not commission_earned) is counted
    """
    try:
        query = select(
            func.coalesce(func.sum(CommissionRecord.commission_charged), Decimal("0"))
        ).where(
            and_(
                CommissionRecord.billing_cycle_id == cycle_id,
                CommissionRecord.billing_phase == BillingPhase.PAID,
                CommissionRecord.status == CommissionStatus.RECORDED,
                CommissionRecord.commission_charged > 0,
            )
        )

        result = await session.execute(query)
        calculated_usage = Decimal(str(result.scalar_one()))

        return calculated_usage
    except Exception as e:
        logger.error(f"Error calculating usage for cycle {cycle_id}: {e}")
        return Decimal("0")


async def fix_billing_cycle_usage(
    shop_id: Optional[str] = None,
    cycle_id: Optional[str] = None,
    only_exceeding_cap: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Fix billing cycle usage amounts by recalculating from RECORDED commissions.

    Args:
        shop_id: Optional shop ID to filter cycles
        cycle_id: Optional specific cycle ID to fix
        only_exceeding_cap: Only fix cycles where usage > cap
        dry_run: If True, only show what would be fixed without making changes

    Returns:
        Summary of fixes applied
    """
    try:
        async with get_transaction_context() as session:
            billing_repo = BillingRepositoryV2(session)

            # Get billing cycles to fix
            if cycle_id:
                # Fix specific cycle
                cycle = await billing_repo.get_billing_cycle_by_id(cycle_id)
                cycles_to_fix = [cycle] if cycle else []
            elif shop_id:
                # Fix all cycles for a shop
                shop_subscription = await billing_repo.get_shop_subscription(shop_id)
                if not shop_subscription:
                    logger.error(f"❌ No subscription found for shop {shop_id}")
                    return {
                        "success": False,
                        "error": f"No subscription found for shop {shop_id}",
                    }

                # Get all cycles for this subscription
                query = (
                    select(BillingCycle)
                    .where(BillingCycle.shop_subscription_id == shop_subscription.id)
                    .order_by(BillingCycle.cycle_number.desc())
                )

                result = await session.execute(query)
                cycles_to_fix = list(result.scalars().all())
            else:
                # Fix all active cycles
                query = select(BillingCycle).where(
                    BillingCycle.status == BillingCycleStatus.ACTIVE
                )
                result = await session.execute(query)
                cycles_to_fix = list(result.scalars().all())

            if not cycles_to_fix:
                logger.info("ℹ️ No billing cycles found to fix")
                return {
                    "success": True,
                    "cycles_checked": 0,
                    "cycles_fixed": 0,
                    "total_usage_corrected": 0.0,
                }

            logger.info(f"📋 Found {len(cycles_to_fix)} billing cycle(s) to check")

            cycles_fixed = 0
            total_usage_corrected = Decimal("0")
            fixes_applied = []

            for cycle in cycles_to_fix:
                try:
                    # Calculate correct usage from RECORDED commissions
                    correct_usage = await calculate_correct_usage(session, cycle.id)
                    current_usage = Decimal(str(cycle.usage_amount))

                    # Check if fix is needed
                    needs_fix = False
                    reason = None

                    if correct_usage != current_usage:
                        needs_fix = True
                        reason = f"Usage mismatch: current=${current_usage}, correct=${correct_usage}"

                    # Also check if usage exceeds cap (but only if only_exceeding_cap is True)
                    if only_exceeding_cap:
                        if correct_usage > cycle.current_cap_amount:
                            needs_fix = True
                            reason = f"Usage exceeds cap: ${correct_usage} > ${cycle.current_cap_amount}"
                        else:
                            needs_fix = False
                            reason = None

                    if not needs_fix:
                        logger.debug(
                            f"✅ Cycle {cycle.id} (shop_subscription: {cycle.shop_subscription_id}) "
                            f"usage is correct: ${current_usage}"
                        )
                        continue

                    # Calculate difference
                    usage_diff = correct_usage - current_usage
                    total_usage_corrected += abs(usage_diff)

                    logger.info(
                        f"🔧 Cycle {cycle.id}: {reason}\n"
                        f"   Current usage: ${current_usage}\n"
                        f"   Correct usage: ${correct_usage}\n"
                        f"   Difference: ${usage_diff:+.2f}"
                    )

                    if not dry_run:
                        # Update the billing cycle
                        cycle_update = (
                            update(BillingCycle)
                            .where(BillingCycle.id == cycle.id)
                            .values(
                                usage_amount=correct_usage,
                                updated_at=now_utc(),
                            )
                        )
                        await session.execute(cycle_update)
                        await session.flush()

                        cycles_fixed += 1
                        fixes_applied.append(
                            {
                                "cycle_id": str(cycle.id),
                                "shop_subscription_id": str(cycle.shop_subscription_id),
                                "old_usage": float(current_usage),
                                "new_usage": float(correct_usage),
                                "difference": float(usage_diff),
                                "current_cap": float(cycle.current_cap_amount),
                                "remaining_cap_before": float(
                                    cycle.current_cap_amount - current_usage
                                ),
                                "remaining_cap_after": float(
                                    cycle.current_cap_amount - correct_usage
                                ),
                            }
                        )

                        logger.info(
                            f"✅ Fixed cycle {cycle.id}: ${current_usage} → ${correct_usage}"
                        )
                    else:
                        cycles_fixed += 1
                        fixes_applied.append(
                            {
                                "cycle_id": str(cycle.id),
                                "shop_subscription_id": str(cycle.shop_subscription_id),
                                "old_usage": float(current_usage),
                                "new_usage": float(correct_usage),
                                "difference": float(usage_diff),
                                "current_cap": float(cycle.current_cap_amount),
                                "remaining_cap_before": float(
                                    cycle.current_cap_amount - current_usage
                                ),
                                "remaining_cap_after": float(
                                    cycle.current_cap_amount - correct_usage
                                ),
                            }
                        )
                        logger.info(
                            f"🔍 [DRY RUN] Would fix cycle {cycle.id}: ${current_usage} → ${correct_usage}"
                        )

                except Exception as e:
                    logger.error(
                        f"❌ Error fixing cycle {cycle.id}: {e}",
                        exc_info=True,
                    )
                    continue

            if dry_run:
                logger.info(
                    f"🔍 [DRY RUN] Would fix {cycles_fixed}/{len(cycles_to_fix)} billing cycles "
                    f"(total usage correction: ${abs(total_usage_corrected):.2f})"
                )
            else:
                logger.info(
                    f"✅ Fixed {cycles_fixed}/{len(cycles_to_fix)} billing cycles "
                    f"(total usage correction: ${abs(total_usage_corrected):.2f})"
                )

            # Transaction will be committed automatically if not dry_run
            return {
                "success": True,
                "dry_run": dry_run,
                "cycles_checked": len(cycles_to_fix),
                "cycles_fixed": cycles_fixed,
                "total_usage_corrected": float(abs(total_usage_corrected)),
                "fixes_applied": fixes_applied,
            }

    except Exception as e:
        logger.error(f"❌ Error fixing billing cycle usage: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


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
