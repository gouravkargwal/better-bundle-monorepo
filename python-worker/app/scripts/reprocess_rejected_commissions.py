"""
Script to manually reprocess rejected commissions for a shop's billing cycle.

Usage:
    python -m app.scripts.reprocess_rejected_commissions --shop-id <shop_id> [--cycle-id <cycle_id>]

Example:
    # Reprocess for current active cycle
    python -m app.scripts.reprocess_rejected_commissions --shop-id "07f76875-7ef1-48ad-858a-28f40f1f3c61"

    # Reprocess for specific cycle
    python -m app.scripts.reprocess_rejected_commissions --shop-id "07f76875-7ef1-48ad-858a-28f40f1f3c61" --cycle-id "abc123"
"""

import asyncio
import argparse
from decimal import Decimal

from app.core.database.session import get_transaction_context
from app.domains.billing.repositories.billing_repository_v2 import BillingRepositoryV2
from app.repository.CommissionRepository import CommissionRepository
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
from app.domains.billing.services.shopify_usage_billing_service_v2 import (
    ShopifyUsageBillingServiceV2,
)
from app.core.database.models.commission import CommissionRecord
from app.core.database.models.enums import ChargeType, CommissionStatus
from sqlalchemy import select, and_, func
from app.shared.helpers import now_utc
from app.core.logging import get_logger

logger = get_logger(__name__)


async def reprocess_rejected_commissions(shop_id: str, cycle_id: str = None):
    """
    Reprocess rejected commissions for a shop's billing cycle.

    Args:
        shop_id: Shop ID to reprocess commissions for
        cycle_id: Optional billing cycle ID. If not provided, uses current active cycle
    """
    try:
        async with get_transaction_context() as session:
            billing_repo = BillingRepositoryV2(session)
            commission_repo = CommissionRepository(session)
            shopify_billing = ShopifyUsageBillingServiceV2(session, billing_repo)
            commission_service = CommissionServiceV2(
                session, billing_repo, commission_repo, shopify_billing
            )

            # Get billing cycle
            if cycle_id:
                current_cycle = await billing_repo.get_billing_cycle_by_id(cycle_id)
                if not current_cycle:
                    logger.error(f"❌ Billing cycle {cycle_id} not found")
                    return
            else:
                # Get current active billing cycle for shop
                shop_subscription = await billing_repo.get_shop_subscription(shop_id)
                if not shop_subscription:
                    logger.error(f"❌ No active subscription found for shop {shop_id}")
                    return

                current_cycle = await billing_repo.get_current_billing_cycle(
                    shop_subscription.id
                )
                if not current_cycle:
                    logger.error(f"❌ No active billing cycle found for shop {shop_id}")
                    return
                cycle_id = current_cycle.id

            logger.info(
                f"🔄 Reprocessing rejected/pending commissions for shop {shop_id}, cycle {cycle_id}"
            )

            # Find REJECTED and PENDING commissions in PAID phase
            # Reprocessing means: re-evaluate charges based on current cap and re-record to Shopify
            query = select(CommissionRecord).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_cycle_id == cycle_id,
                    CommissionRecord.billing_phase == "PAID",
                    # Include REJECTED commissions and PENDING commissions
                    (
                        (CommissionRecord.status == CommissionStatus.REJECTED)
                        | (CommissionRecord.status == CommissionStatus.PENDING)
                    ),
                )
            )

            result = await session.execute(query)
            commissions_to_reprocess = result.scalars().all()

            if not commissions_to_reprocess:
                logger.info(
                    f"ℹ️ No rejected/pending commissions to reprocess for cycle {cycle_id}"
                )
                return

            logger.info(
                f"📋 Found {len(commissions_to_reprocess)} commissions (REJECTED + PENDING) to reprocess"
            )

            # Calculate remaining cap
            remaining_cap = Decimal(current_cycle.current_cap_amount) - Decimal(
                current_cycle.usage_amount
            )

            logger.info(f"💰 Remaining cap: ${remaining_cap}")

            total_reprocessed = 0
            total_charged = Decimal("0")
            errors = []

            # Process each commission
            for commission in commissions_to_reprocess:
                try:
                    # Re-evaluate charge amounts based on current cap
                    # Always recalculate from commission_earned to account for cap changes
                    amount_to_charge = Decimal(commission.commission_earned)

                    # Use commission service's charge calculation logic
                    charge_data = commission_service._calculate_charge_amounts(
                        amount_to_charge, remaining_cap
                    )

                    # Update commission record
                    commission.commission_charged = charge_data["actual_charge"]
                    commission.commission_overflow = charge_data["overflow"]
                    commission.charge_type = charge_data["charge_type"]
                    commission.status = (
                        CommissionStatus.PENDING
                    )  # Reset to pending for re-recording
                    commission.updated_at = now_utc()

                    await session.flush()

                    # Record to Shopify if there's a charge amount
                    if commission.commission_charged > 0:
                        logger.info(
                            f"🎯 Re-recording commission {commission.id} to Shopify (charge: ${commission.commission_charged})"
                        )

                        # Record to Shopify
                        record_result = (
                            await commission_service.record_commission_to_shopify(
                                commission_id=commission.id,
                                shopify_billing_service=shopify_billing,
                            )
                        )

                        if record_result.get("success"):
                            total_charged += commission.commission_charged
                            remaining_cap -= commission.commission_charged
                            total_reprocessed += 1
                            logger.info(
                                f"✅ Successfully re-recorded commission {commission.id} to Shopify"
                            )
                        else:
                            # If Shopify recording failed, mark as REJECTED
                            commission.charge_type = ChargeType.REJECTED
                            commission.status = CommissionStatus.REJECTED
                            # Restore overflow amount
                            commission.commission_overflow = (
                                commission.commission_overflow
                                + commission.commission_charged
                            )
                            commission.commission_charged = Decimal("0")
                            error_msg = record_result.get("error", "Unknown error")
                            errors.append(
                                {
                                    "commission_id": str(commission.id),
                                    "error": error_msg,
                                }
                            )
                            logger.warning(
                                f"⚠️ Failed to record commission {commission.id} to Shopify: {error_msg}"
                            )
                            await session.flush()
                    else:
                        # No charge amount - mark as REJECTED if needed
                        if charge_data["overflow"] > 0:
                            commission.charge_type = ChargeType.REJECTED
                            commission.status = CommissionStatus.REJECTED
                            logger.info(
                                f"⚠️ Commission {commission.id} still has no charge amount (overflow: ${charge_data['overflow']}), marking as REJECTED"
                            )
                            await session.flush()

                    # Stop processing if no remaining cap
                    if remaining_cap <= 0:
                        logger.info(
                            f"⚠️ Remaining cap exhausted. Stopping reprocessing. {len(commissions_to_reprocess) - total_reprocessed - 1} commissions remaining."
                        )
                        break

                except Exception as e:
                    errors.append(
                        {
                            "commission_id": str(commission.id),
                            "error": str(e),
                        }
                    )
                    logger.error(
                        f"❌ Error reprocessing commission {commission.id}: {e}",
                        exc_info=True,
                    )

            # Update billing cycle usage
            if total_charged > 0:
                await billing_repo.update_billing_cycle_usage(cycle_id, total_charged)
                logger.info(f"💰 Updated billing cycle usage: ${total_charged}")

            # Transaction will be committed automatically by get_transaction_context()
            logger.info(
                f"✅ Reprocessing complete: {total_reprocessed}/{len(commissions_to_reprocess)} commissions reprocessed, ${total_charged} charged"
            )

            if errors:
                logger.warning(f"⚠️ {len(errors)} commissions had errors:")
                for error in errors:
                    logger.warning(
                        f"  - Commission {error['commission_id']}: {error['error']}"
                    )

    except Exception as e:
        logger.error(f"❌ Error reprocessing rejected commissions: {e}", exc_info=True)
        raise


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Reprocess rejected commissions for a shop's billing cycle"
    )
    parser.add_argument(
        "--shop-id",
        required=True,
        help="Shop ID to reprocess commissions for",
    )
    parser.add_argument(
        "--cycle-id",
        help="Optional billing cycle ID. If not provided, uses current active cycle",
    )

    args = parser.parse_args()

    asyncio.run(reprocess_rejected_commissions(args.shop_id, args.cycle_id))


if __name__ == "__main__":
    main()
