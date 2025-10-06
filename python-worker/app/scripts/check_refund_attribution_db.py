#!/usr/bin/env python3
"""
Script to check if refund attribution records exist in the database
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.database.session import get_session_context
from app.core.database.models.refund_attribution import RefundAttribution
from sqlalchemy import select, and_


async def check_refund_attribution_records():
    """Check if refund attribution records exist in the database."""
    async with get_session_context() as session:
        # Get all refund attribution records
        query = select(RefundAttribution).where(
            RefundAttribution.shop_id == "cmgem0tut0000v3h2h38lsh1y"
        )
        result = await session.execute(query)
        refund_attributions = result.scalars().all()

        print(f"Found {len(refund_attributions)} refund attribution records:")

        for refund_attribution in refund_attributions:
            print(f"  - Refund ID: {refund_attribution.refund_id}")
            print(f"    Order ID: {refund_attribution.order_id}")
            print(f"    Refunded At: {refund_attribution.refunded_at}")
            print(f"    Total Refund Amount: {refund_attribution.total_refund_amount}")
            print(f"    Currency: {refund_attribution.currency_code}")
            print(
                f"    Total Refunded Revenue: {refund_attribution.total_refunded_revenue}"
            )
            print(
                f"    Contributing Extensions: {refund_attribution.contributing_extensions}"
            )
            print(f"    Attribution Weights: {refund_attribution.attribution_weights}")
            print(f"    Attributed Refund: {refund_attribution.attributed_refund}")
            print(f"    Total Interactions: {refund_attribution.total_interactions}")
            print(
                f"    Interactions by Extension: {refund_attribution.interactions_by_extension}"
            )
            print(
                f"    Attribution Algorithm: {refund_attribution.attribution_algorithm}"
            )
            print(f"    Metadata: {refund_attribution.attribution_metadata}")
            print("    ---")


if __name__ == "__main__":
    asyncio.run(check_refund_attribution_records())
