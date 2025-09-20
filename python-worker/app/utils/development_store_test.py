"""
Development Store Test Data Setup

This module adds comprehensive test data for existing development stores
to test real billing scenarios.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from prisma import Json

logger = logging.getLogger(__name__)


async def add_test_data_for_existing_shops() -> Dict[str, Any]:
    """
    Add comprehensive test data for existing shops in the database.
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        logger.info("🚀 Adding test data for existing shops...")

        # Get all existing shops (not test shops)
        test_shop_ids = [
            "test-trial-shop",
            "test-progress-shop",
            "test-completed-trial",
            "test-regular-shop",
        ]
        existing_shops = await db.shop.find_many(
            where={"id": {"not": {"in": test_shop_ids}}}
        )

        if not existing_shops:
            return {
                "status": "info",
                "message": "No existing shops found to add test data to",
                "shops_processed": 0,
            }

        results = []

        for shop in existing_shops:
            try:
                # Add test data for this shop
                result = await add_test_data_for_shop(db, shop)
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to add test data for shop {shop.id}: {e}")
                results.append(
                    {
                        "shop_id": shop.id,
                        "shop_domain": shop.shopDomain,
                        "status": "error",
                        "error": str(e),
                    }
                )

        logger.info(f"✅ Added test data for {len(results)} shops")

        return {
            "status": "success",
            "message": "Test data added for existing shops",
            "shops_processed": len(results),
            "results": results,
            "created_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to add test data for existing shops: {e}")
        return {
            "status": "error",
            "message": str(e),
            "shops_processed": 0,
            "results": [],
        }


async def add_test_data_for_shop(db, shop) -> Dict[str, Any]:
    """Add comprehensive test data for a specific shop"""
    try:
        shop_id = shop.id
        shop_domain = shop.shopDomain

        logger.info(f"📊 Adding test data for shop: {shop_domain}")

        # Check if shop has billing plan
        billing_plan = await db.billingplan.find_first(where={"shopId": shop.id})

        if not billing_plan:
            # Create a trial billing plan for this shop
            billing_plan = await db.billingplan.create(
                {
                    "shopId": shop_id,
                    "shopDomain": shop_domain,
                    "name": "Free Trial Plan",
                    "type": "revenue_share",
                    "status": "active",
                    "configuration": Json(
                        {
                            "revenue_share_rate": 0.03,
                            "trial_threshold": 200.0,
                            "trial_active": True,
                        }
                    ),
                    "effectiveFrom": datetime.utcnow(),
                    "isTrialActive": True,
                    "trialThreshold": 200.0,
                    "trialRevenue": 0.0,
                }
            )
            logger.info(f"✅ Created trial billing plan for {shop_domain}")

        # Add realistic interaction events
        interaction_count = 20
        purchase_count = 8
        await create_realistic_interaction_events(
            db, shop_id, interaction_count, purchase_count
        )

        # Add realistic purchase events with attribution
        total_revenue = 350.0  # $350 total revenue
        await create_realistic_purchase_events(db, shop_id, total_revenue)

        # Update trial revenue in billing plan
        await db.billingplan.update(
            where={"id": billing_plan.id}, data={"trialRevenue": total_revenue}
        )

        return {
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "status": "success",
            "interaction_events": interaction_count,
            "purchase_events": purchase_count,
            "total_revenue": total_revenue,
            "trial_revenue": total_revenue,
            "trial_threshold": 200.0,
            "trial_progress": (total_revenue / 200.0) * 100,
            "is_trial_active": True,
        }

    except Exception as e:
        logger.error(f"Failed to add test data for shop {shop.id}: {e}")
        return {
            "shop_id": shop.id,
            "shop_domain": shop.shopDomain,
            "status": "error",
            "error": str(e),
        }


async def create_realistic_interaction_events(
    db, shop_id: str, count: int, purchase_count: int
) -> None:
    """Create realistic interaction events"""
    events = []

    # Product catalog for realistic data
    products = [
        {"id": "prod-1", "title": "Wireless Headphones", "category": "Electronics"},
        {"id": "prod-2", "title": "Smart Watch", "category": "Electronics"},
        {"id": "prod-3", "title": "Coffee Maker", "category": "Home"},
        {"id": "prod-4", "title": "Yoga Mat", "category": "Fitness"},
        {"id": "prod-5", "title": "Bluetooth Speaker", "category": "Electronics"},
    ]

    for i in range(count):
        product = products[i % len(products)]
        event_type = "purchase" if i < purchase_count else "view"

        # Create realistic timestamps (spread over last 7 days)
        hours_ago = (i % 7) * 24 + (i % 24)

        events.append(
            {
                "shopId": shop_id,
                "eventType": event_type,
                "productId": product["id"],
                "customerId": f"customer-{i % 5 + 1}",  # 5 different customers
                "sessionId": f"session-{i % 10 + 1}",  # 10 different sessions
                "timestamp": datetime.utcnow() - timedelta(hours=hours_ago),
                "metadata": Json(
                    {
                        "source": "recommendation_engine",
                        "recommendation_id": f"rec-{i}",
                        "confidence_score": 0.7 + (i % 3) * 0.1,  # 0.7-0.9 confidence
                        "product_category": product["category"],
                        "recommendation_type": "collaborative_filtering",
                    }
                ),
            }
        )

    await db.interactionevent.create_many(events)
    logger.info(f"✅ Created {len(events)} interaction events for shop {shop_id}")


async def create_realistic_purchase_events(
    db, shop_id: str, total_revenue: float
) -> None:
    """Create realistic purchase events with attribution"""
    # Split revenue across multiple purchases
    purchase_amounts = [
        45.99,
        89.50,
        125.00,
        67.25,
        22.26,
    ]  # Realistic purchase amounts

    events = []

    for i, amount in enumerate(purchase_amounts):
        if sum(purchase_amounts[: i + 1]) > total_revenue:
            # Adjust last purchase to match total revenue
            amount = total_revenue - sum(purchase_amounts[:i])
            if amount <= 0:
                break

        # Create realistic product data
        products = [
            {
                "id": "prod-1",
                "title": "Wireless Headphones",
                "price": amount,
                "quantity": 1,
            },
        ]

        # Add multiple products for larger purchases
        if amount > 50:
            products.append(
                {
                    "id": "prod-2",
                    "title": "Protection Plan",
                    "price": amount * 0.1,
                    "quantity": 1,
                }
            )
            products[0]["price"] = amount * 0.9

        events.append(
            {
                "shopId": shop_id,
                "orderId": f"order-{shop_id}-{i+1}",
                "customerId": f"customer-{i % 3 + 1}",
                "sessionId": f"session-{i % 5 + 1}",
                "totalAmount": amount,
                "currency": "USD",
                "products": Json(products),
                "createdAt": datetime.utcnow()
                - timedelta(hours=i * 6),  # Spread over time
                "attributedRevenue": amount,  # Full attribution for testing
            }
        )

    await db.purchaseevent.create_many(events)
    logger.info(
        f"✅ Created {len(events)} purchase events for shop {shop_id} with total revenue ${total_revenue}"
    )


async def get_existing_shops_summary(db) -> Dict[str, Any]:
    """Get summary of existing shops with their test data"""
    try:
        # Get all existing shops (not test shops)
        test_shop_ids = [
            "test-trial-shop",
            "test-progress-shop",
            "test-completed-trial",
            "test-regular-shop",
        ]
        existing_shops = await db.shop.find_many(
            where={"id": {"not": {"in": test_shop_ids}}}
        )

        summary = []
        for shop in existing_shops:
            # Get billing plan for this shop
            billing_plan = await db.billingplan.find_first(where={"shopId": shop.id})

            summary.append(
                {
                    "shop_id": shop.id,
                    "shop_domain": shop.shopDomain,
                    "has_billing_plan": billing_plan is not None,
                    "trial_active": (
                        billing_plan.isTrialActive if billing_plan else False
                    ),
                    "trial_revenue": (
                        float(billing_plan.trialRevenue) if billing_plan else 0
                    ),
                    "trial_threshold": (
                        float(billing_plan.trialThreshold) if billing_plan else 0
                    ),
                }
            )

        return {
            "status": "success",
            "existing_shops": len(existing_shops),
            "summary": summary,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


if __name__ == "__main__":

    async def main():
        result = await add_test_data_for_existing_shops()
        print(f"Development store test data result: {result}")

    asyncio.run(main())
