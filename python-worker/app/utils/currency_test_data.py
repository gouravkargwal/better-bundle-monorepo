"""
Currency Test Data Setup

This module creates test data with different currencies to test multi-currency billing.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from prisma import Json

logger = logging.getLogger(__name__)


async def create_currency_test_data() -> Dict[str, Any]:
    """
    Create test data with different currencies to test multi-currency billing.
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        logger.info("🌍 Creating currency test data...")

        # Clean up existing currency test data
        await cleanup_currency_test_data(db)

        results = []

        # 1. US Store (USD)
        usd_result = await create_currency_shop(
            db, "test-usd-shop", "usd-shop.myshopify.com", "USD", 1000.0
        )
        results.append(usd_result)

        # 2. European Store (EUR)
        eur_result = await create_currency_shop(
            db, "test-eur-shop", "eur-shop.myshopify.com", "EUR", 800.0
        )
        results.append(eur_result)

        # 3. UK Store (GBP)
        gbp_result = await create_currency_shop(
            db, "test-gbp-shop", "gbp-shop.myshopify.com", "GBP", 600.0
        )
        results.append(gbp_result)

        # 4. Canadian Store (CAD)
        cad_result = await create_currency_shop(
            db, "test-cad-shop", "cad-shop.myshopify.com", "CAD", 1200.0
        )
        results.append(cad_result)

        logger.info(f"✅ Created {len(results)} currency test scenarios")

        return {
            "status": "success",
            "message": "Currency test data created",
            "scenarios_created": len(results),
            "results": results,
            "created_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to create currency test data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "scenarios_created": 0,
            "results": [],
        }


async def cleanup_currency_test_data(db) -> None:
    """Clean up existing currency test data"""
    test_shop_ids = ["test-usd-shop", "test-eur-shop", "test-gbp-shop", "test-cad-shop"]

    # Delete in reverse order to handle foreign key constraints
    await db.billingevent.delete_many(where={"shopId": {"in": test_shop_ids}})
    await db.billinginvoice.delete_many(where={"shopId": {"in": test_shop_ids}})
    await db.billingplan.delete_many(where={"shopId": {"in": test_shop_ids}})
    await db.shop.delete_many(where={"id": {"in": test_shop_ids}})

    logger.info("🧹 Cleaned up existing currency test data")


async def create_currency_shop(
    db, shop_id: str, shop_domain: str, currency: str, revenue: float
) -> Dict[str, Any]:
    """Create a shop with specific currency and revenue"""
    try:
        # Create shop with currency
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": shop_domain,
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": f"owner@{shop_domain}",
                "currencyCode": currency,
                "planType": "Basic",
            }
        )

        # Create billing plan (no trial for currency testing)
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": shop_domain,
                "name": f"Standard Plan ({currency})",
                "type": "revenue_share",
                "status": "active",
                "configuration": Json(
                    {
                        "revenue_share_rate": 0.03,
                        "trial_threshold": 0.0,
                        "trial_active": False,
                    }
                ),
                "effectiveFrom": datetime.utcnow(),
                "isTrialActive": False,
                "trialThreshold": 0.0,
                "trialRevenue": 0.0,
            }
        )

        # Create some interaction events
        await create_interaction_events(db, shop_id, 10, 5)

        # Create purchase events with revenue
        await create_purchase_events(db, shop_id, revenue, currency)

        return {
            "scenario": f"{currency} Store",
            "status": "success",
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "currency": currency,
            "revenue": revenue,
            "expected_fee": revenue * 0.03,
            "is_trial_active": False,
        }

    except Exception as e:
        return {
            "scenario": f"{currency} Store",
            "status": "error",
            "error": str(e),
        }


async def create_interaction_events(
    db, shop_id: str, count: int, purchase_count: int
) -> None:
    """Create interaction events for a shop"""
    # First create user sessions
    sessions = []
    for i in range(count):
        session_id = f"session-{shop_id}-{i}"
        sessions.append(
            {
                "id": session_id,
                "shopId": shop_id,
                "customerId": f"customer-{i % 3 + 1}",
                "browserSessionId": f"browser-{shop_id}-{i}",
                "createdAt": datetime.utcnow() - timedelta(hours=i),
                "lastActive": (
                    datetime.utcnow() - timedelta(hours=i - 1)
                    if i > 0
                    else datetime.utcnow() - timedelta(hours=i)
                ),
                "expiresAt": datetime.utcnow() + timedelta(hours=24),
                "userAgent": "Mozilla/5.0 (Test Browser)",
                "ipAddress": "127.0.0.1",
                "extensionsUsed": Json(["recommendation_engine"]),
                "totalInteractions": 5,
            }
        )

    await db.usersession.create_many(sessions)

    # Then create interactions
    events = []
    for i in range(count):
        event_type = "purchase" if i < purchase_count else "view"

        events.append(
            {
                "sessionId": f"session-{shop_id}-{i}",
                "extensionType": "recommendation_engine",
                "interactionType": event_type,
                "customerId": f"customer-{i % 3 + 1}",
                "shopId": shop_id,
                "metadata": Json(
                    {
                        "product_id": f"product-{i % 5 + 1}",
                        "recommendation_id": f"rec-{i}",
                        "confidence_score": 0.8 + (i % 3) * 0.1,
                    }
                ),
            }
        )

    await db.userinteraction.create_many(events)


async def create_purchase_events(
    db, shop_id: str, total_revenue: float, currency: str
) -> None:
    """Create purchase events with attribution for a shop"""
    # Split revenue across multiple purchases
    purchase_count = max(1, int(total_revenue / 100))  # ~$100 per purchase
    amount_per_purchase = total_revenue / purchase_count

    events = []

    for i in range(purchase_count):
        events.append(
            {
                "sessionId": f"session-{shop_id}-{i % 5}",
                "orderId": f"order-{shop_id}-{i+1}",
                "customerId": f"customer-{i % 3 + 1}",
                "shopId": shop_id,
                "contributingExtensions": Json(["recommendation_engine"]),
                "attributionWeights": Json({"recommendation_engine": 1.0}),
                "totalRevenue": amount_per_purchase,
                "attributedRevenue": Json(
                    {"recommendation_engine": amount_per_purchase}
                ),
                "totalInteractions": 5,
                "interactionsByExtension": Json({"recommendation_engine": 5}),
                "purchaseAt": datetime.utcnow() - timedelta(hours=i * 6),
                "attributionAlgorithm": "multi_touch",
                "metadata": Json(
                    {
                        "currency": currency,
                        "test_data": True,
                    }
                ),
            }
        )

    await db.purchaseattribution.create_many(events)


async def get_currency_test_summary(db) -> Dict[str, Any]:
    """Get summary of currency test data"""
    try:
        # Get all currency test shops
        test_shop_ids = [
            "test-usd-shop",
            "test-eur-shop",
            "test-gbp-shop",
            "test-cad-shop",
        ]
        test_shops = await db.shop.find_many(where={"id": {"in": test_shop_ids}})

        summary = []
        for shop in test_shops:
            # Get billing plan for this shop
            billing_plan = await db.billingplan.find_first(where={"shopId": shop.id})

            # Get total attributed revenue
            purchase_events = await db.purchaseattribution.find_many(
                where={"shopId": shop.id}
            )
            total_revenue = sum(event.totalRevenue for event in purchase_events)

            summary.append(
                {
                    "shop_id": shop.id,
                    "shop_domain": shop.shopDomain,
                    "currency": shop.currencyCode,
                    "total_revenue": float(total_revenue),
                    "expected_fee": float(total_revenue) * 0.03,
                    "trial_active": (
                        billing_plan.isTrialActive if billing_plan else False
                    ),
                }
            )

        return {
            "status": "success",
            "test_shops": len(test_shops),
            "summary": summary,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


if __name__ == "__main__":

    async def main():
        result = await create_currency_test_data()
        print(f"Currency test data result: {result}")

    asyncio.run(main())
