#!/usr/bin/env python3
"""
Check trial revenue and refund attribution data
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database.session import get_session
from app.core.database.models import RefundAttribution, RefundData, PurchaseAttribution
from app.core.database.models.billing import BillingPlan
from sqlalchemy import select, and_


async def check_trial_revenue():
    """Check trial revenue and refund attribution data"""

    session = await get_session()
    try:
        # First, let's check what tables exist and what data is in them
        print("🔍 Checking database tables and data...")

        # Check if we can query basic tables
        from app.core.database.models import Shop

        shops_query = select(Shop)
        shops_result = await session.execute(shops_query)
        shops = shops_result.scalars().all()
        print(f"Found {len(shops)} shops in database")

        if shops:
            print("Shop IDs found:")
            for shop in shops:
                print(f"   - {shop.id}")

        # Check RefundData table
        refund_data_query = select(RefundData)
        refund_data_result = await session.execute(refund_data_query)
        refund_data_records = refund_data_result.scalars().all()
        print(f"Found {len(refund_data_records)} refund data records")

        if refund_data_records:
            print("Refund Data records:")
            for refund in refund_data_records:
                print(
                    f"   - Order ID: {refund.order_id}, Refund ID: {refund.refund_id}, Amount: ${refund.total_refund_amount}"
                )

        print("\n" + "=" * 50)
        # Get all billing plans to see what shop IDs exist
        all_billing_plans_query = select(BillingPlan)
        all_billing_plans_result = await session.execute(all_billing_plans_query)
        all_billing_plans = all_billing_plans_result.scalars().all()

        print(f"Found {len(all_billing_plans)} billing plans:")
        for plan in all_billing_plans:
            print(
                f"   Shop ID: {plan.shop_id}, Trial Revenue: ${plan.trial_revenue}, Status: {plan.status}"
            )

        # Use the first one if any exist
        billing_plan = all_billing_plans[0] if all_billing_plans else None

        if billing_plan:
            print(f"✅ Billing Plan Found:")
            print(f"   Shop ID: {billing_plan.shop_id}")
            print(f"   Trial Revenue: ${billing_plan.trial_revenue}")
            print(f"   Trial Threshold: ${billing_plan.trial_threshold}")
            print(f"   Is Trial Active: {billing_plan.is_trial_active}")
            print(f"   Status: {billing_plan.status}")
        else:
            print("❌ No billing plan found - continuing to check refund data...")

        # Get all refund attributions to see what exists
        all_refund_attributions_query = select(RefundAttribution)
        all_refund_attributions_result = await session.execute(
            all_refund_attributions_query
        )
        all_refund_attributions = all_refund_attributions_result.scalars().all()

        print(f"\nFound {len(all_refund_attributions)} refund attributions:")
        for refund_attr in all_refund_attributions:
            print(f"   Order ID: {refund_attr.order_id}")
            print(f"   Refund ID: {refund_attr.refund_id}")
            print(f"   Attribution Weights: {refund_attr.attribution_weights}")
            print(f"   Attributed Refund: {refund_attr.attributed_refund}")
            print(f"   Total Refunded Revenue: ${refund_attr.total_refunded_revenue}")
            print("   ---")

        # Get specific refund attribution for order 6108064612491
        refund_attribution_query = select(RefundAttribution).where(
            RefundAttribution.order_id == "6108064612491"
        )
        refund_attribution_result = await session.execute(refund_attribution_query)
        refund_attribution = refund_attribution_result.scalar_one_or_none()

        if refund_attribution:
            print(f"\n✅ Specific Refund Attribution for Order 6108064612491:")
            print(f"   Order ID: {refund_attribution.order_id}")
            print(f"   Refund ID: {refund_attribution.refund_id}")
            print(f"   Total Refund Amount: ${refund_attribution.total_refund_amount}")
            print(f"   Attribution Weights: {refund_attribution.attribution_weights}")
            print(f"   Attributed Refund: {refund_attribution.attributed_refund}")
            print(
                f"   Total Refunded Revenue: ${refund_attribution.total_refunded_revenue}"
            )
        else:
            print("\n❌ No refund attribution found for order 6108064612491")

        # Get original purchase attribution
        purchase_attribution_query = select(PurchaseAttribution).where(
            PurchaseAttribution.order_id == "6108064612491"
        )
        purchase_attribution_result = await session.execute(purchase_attribution_query)
        purchase_attribution = purchase_attribution_result.scalar_one_or_none()

        if purchase_attribution:
            print(f"\n✅ Original Purchase Attribution:")
            print(f"   Order ID: {purchase_attribution.order_id}")
            print(f"   Total Revenue: ${purchase_attribution.total_revenue}")
            print(f"   Attribution Weights: {purchase_attribution.attribution_weights}")
            print(f"   Attributed Revenue: {purchase_attribution.attributed_revenue}")
        else:
            print("\n❌ No original purchase attribution found")

        # Calculate what should have happened
        if refund_attribution and purchase_attribution:
            print(f"\n🔍 ANALYSIS:")

            # Original attributed revenue
            original_attributed = (
                sum(purchase_attribution.attributed_revenue.values())
                if purchase_attribution.attributed_revenue
                else 0
            )
            print(f"   Original Attributed Revenue: ${original_attributed}")

            # Refunded attributed revenue
            refunded_attributed = (
                sum(refund_attribution.attributed_refund.values())
                if refund_attribution.attributed_refund
                else 0
            )
            print(f"   Refunded Attributed Revenue: ${refunded_attributed}")

            # Expected trial revenue change
            expected_change = -refunded_attributed
            print(f"   Expected Trial Revenue Change: ${expected_change}")

            if expected_change != 0:
                print(
                    f"   ❌ ISSUE: Trial revenue should have decreased by ${abs(expected_change)}"
                )
            else:
                print(f"   ✅ Trial revenue change is correct")

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(check_trial_revenue())
