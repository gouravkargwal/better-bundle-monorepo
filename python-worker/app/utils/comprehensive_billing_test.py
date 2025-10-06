"""
Comprehensive Billing Test Data Setup

This module creates realistic test data for billing scenarios including:
- Real revenue data
- Attribution events
- Purchase events
- Billing calculations
- Trial scenarios
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from prisma import Json

logger = logging.getLogger(__name__)


async def create_comprehensive_billing_test_data() -> Dict[str, Any]:
    """
    Create comprehensive test data for billing scenarios.
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        logger.info("🚀 Creating comprehensive billing test data...")

        # Clean up existing test data first
        await cleanup_test_data(db)

        results = []

        # 1. Trial Shop - No revenue yet
        trial_shop_result = await create_trial_shop_scenario(db)
        results.append(trial_shop_result)

        # 2. Trial Shop - Some revenue but under threshold
        progress_shop_result = await create_trial_progress_scenario(db)
        results.append(progress_shop_result)

        # 3. Trial Shop - Over threshold, should be billed
        completed_trial_result = await create_completed_trial_scenario(db)
        results.append(completed_trial_result)

        # 4. Regular Shop - Active billing
        regular_shop_result = await create_regular_billing_scenario(db)
        results.append(regular_shop_result)

        # 5. High Revenue Shop - Tier 2 billing
        high_revenue_result = await create_high_revenue_scenario(db)
        results.append(high_revenue_result)

        logger.info(f"✅ Created {len(results)} billing test scenarios")

        return {
            "status": "success",
            "message": "Comprehensive billing test data created",
            "scenarios_created": len(results),
            "results": results,
            "created_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to create comprehensive billing test data: {e}")
        return {
            "status": "error",
            "message": str(e),
            "scenarios_created": 0,
            "results": [],
        }


async def cleanup_test_data(db) -> None:
    """Clean up existing test data"""
    test_shop_ids = [
        "test-trial-shop",
        "test-progress-shop",
        "test-completed-trial",
        "test-regular-shop",
        "test-high-revenue-shop",
    ]

    # Delete in reverse order to handle foreign key constraints
    await db.billinginvoice.delete_many(where={"shopId": {"in": test_shop_ids}})
    await db.billingplan.delete_many(where={"shopId": {"in": test_shop_ids}})
    await db.shop.delete_many(where={"id": {"in": test_shop_ids}})

    logger.info("🧹 Cleaned up existing test data")


async def create_trial_shop_scenario(db) -> Dict[str, Any]:
    """Create a shop in trial with no revenue"""
    try:
        shop_id = "test-trial-shop"

        # Create shop
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": "trial-shop.myshopify.com",
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": "owner@trial-shop.myshopify.com",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create trial billing plan
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": "trial-shop.myshopify.com",
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

        # Create some interaction events (no purchases yet)
        await create_interaction_events(db, shop_id, 5, 0)

        return {
            "scenario": "Trial Shop - No Revenue",
            "status": "success",
            "shop_id": shop_id,
            "trial_revenue": 0.0,
            "trial_threshold": 200.0,
            "is_trial_active": True,
        }

    except Exception as e:
        return {
            "scenario": "Trial Shop - No Revenue",
            "status": "error",
            "error": str(e),
        }


async def create_trial_progress_scenario(db) -> Dict[str, Any]:
    """Create a shop in trial with some revenue"""
    try:
        shop_id = "test-progress-shop"

        # Create shop
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": "progress-shop.myshopify.com",
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": "owner@progress-shop.myshopify.com",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create trial billing plan
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": "progress-shop.myshopify.com",
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
                "trialRevenue": 150.0,  # $150 revenue, $50 to go
            }
        )

        # Create interaction and purchase events
        await create_interaction_events(db, shop_id, 10, 3)
        await create_purchase_events(db, shop_id, 150.0)

        return {
            "scenario": "Trial Shop - Progress",
            "status": "success",
            "shop_id": shop_id,
            "trial_revenue": 150.0,
            "trial_threshold": 200.0,
            "is_trial_active": True,
        }

    except Exception as e:
        return {
            "scenario": "Trial Shop - Progress",
            "status": "error",
            "error": str(e),
        }


async def create_completed_trial_scenario(db) -> Dict[str, Any]:
    """Create a shop that has completed trial and should be billed"""
    try:
        shop_id = "test-completed-trial"

        # Create shop
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": "completed-trial.myshopify.com",
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": "owner@completed-trial.myshopify.com",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create completed trial billing plan
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": "completed-trial.myshopify.com",
                "name": "Standard Revenue Share Plan",
                "type": "revenue_share",
                "status": "active",
                "configuration": Json(
                    {
                        "revenue_share_rate": 0.03,
                        "trial_threshold": 200.0,
                        "trial_active": False,
                    }
                ),
                "effectiveFrom": datetime.utcnow(),
                "isTrialActive": False,  # Trial completed
                "trialThreshold": 200.0,
                "trialRevenue": 250.0,  # Exceeded threshold
            }
        )

        # Create substantial interaction and purchase events
        await create_interaction_events(db, shop_id, 25, 8)
        await create_purchase_events(db, shop_id, 250.0)

        return {
            "scenario": "Completed Trial - Should Be Billed",
            "status": "success",
            "shop_id": shop_id,
            "trial_revenue": 250.0,
            "trial_threshold": 200.0,
            "is_trial_active": False,
        }

    except Exception as e:
        return {
            "scenario": "Completed Trial - Should Be Billed",
            "status": "error",
            "error": str(e),
        }


async def create_regular_billing_scenario(db) -> Dict[str, Any]:
    """Create a regular shop with active billing"""
    try:
        shop_id = "test-regular-shop"

        # Create shop
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": "regular-shop.myshopify.com",
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": "owner@regular-shop.myshopify.com",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create regular billing plan (no trial)
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": "regular-shop.myshopify.com",
                "name": "Standard Revenue Share Plan",
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

        # Create interaction and purchase events
        await create_interaction_events(db, shop_id, 15, 5)
        await create_purchase_events(db, shop_id, 500.0)

        return {
            "scenario": "Regular Shop - Active Billing",
            "status": "success",
            "shop_id": shop_id,
            "expected_fee": 15.0,  # 3% of $500
            "is_trial_active": False,
        }

    except Exception as e:
        return {
            "scenario": "Regular Shop - Active Billing",
            "status": "error",
            "error": str(e),
        }


async def create_high_revenue_scenario(db) -> Dict[str, Any]:
    """Create a high-revenue shop for tier testing"""
    try:
        shop_id = "test-high-revenue-shop"

        # Create shop
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": "high-revenue.myshopify.com",
                "accessToken": f"test-token-{shop_id}",
                "isActive": True,
                "email": "owner@high-revenue.myshopify.com",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create high-revenue billing plan
        billing_plan = await db.billingplan.create(
            {
                "shopId": shop_id,
                "shopDomain": "high-revenue.myshopify.com",
                "name": "High Volume Plan",
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

        # Create lots of interaction and purchase events
        await create_interaction_events(db, shop_id, 50, 20)
        await create_purchase_events(db, shop_id, 2000.0)

        return {
            "scenario": "High Revenue Shop",
            "status": "success",
            "shop_id": shop_id,
            "expected_fee": 60.0,  # 3% of $2000
            "is_trial_active": False,
        }

    except Exception as e:
        return {
            "scenario": "High Revenue Shop",
            "status": "error",
            "error": str(e),
        }


async def create_interaction_events(
    db, shop_id: str, count: int, purchase_count: int
) -> None:
    """Create interaction events for a shop"""
    events = []

    for i in range(count):
        event_type = "purchase" if i < purchase_count else "view"

        events.append(
            {
                "shopId": shop_id,
                "eventType": event_type,
                "productId": f"product-{i % 5 + 1}",
                "customerId": f"customer-{i % 3 + 1}",
                "sessionId": f"session-{i}",
                "timestamp": datetime.utcnow() - timedelta(hours=i),
                "metadata": Json(
                    {
                        "source": "recommendation_engine",
                        "recommendation_id": f"rec-{i}",
                        "confidence_score": 0.8 + (i % 3) * 0.1,
                    }
                ),
            }
        )

    await db.userinteraction.create_many(events)


async def create_purchase_events(db, shop_id: str, total_amount: float) -> None:
    """Create purchase events for a shop"""
    # Split total amount across multiple purchases
    purchase_count = max(1, int(total_amount / 50))  # ~$50 per purchase
    amount_per_purchase = total_amount / purchase_count

    events = []

    for i in range(purchase_count):
        events.append(
            {
                "shopId": shop_id,
                "orderId": f"order-{shop_id}-{i}",
                "customerId": f"customer-{i % 3 + 1}",
                "sessionId": f"session-{i}",
                "totalAmount": amount_per_purchase,
                "currency": "USD",
                "products": Json(
                    [
                        {
                            "id": f"product-{i % 5 + 1}",
                            "title": f"Test Product {i % 5 + 1}",
                            "price": amount_per_purchase,
                            "quantity": 1,
                        }
                    ]
                ),
                "createdAt": datetime.utcnow() - timedelta(hours=i),
                "attributedRevenue": amount_per_purchase,  # Full attribution for testing
            }
        )

    await db.purchaseattribution.create_many(events)


async def get_billing_test_summary(db) -> Dict[str, Any]:
    """Get summary of all test billing data"""
    try:
        # Get all test shops
        test_shops = await db.shop.find_many(
            where={"id": {"starts_with": "test-"}},
            include={
                "billingPlans": True,
                "interactionEvents": True,
                "purchaseEvents": True,
            },
        )

        summary = []
        for shop in test_shops:
            total_revenue = sum(
                event.attributedRevenue for event in shop.purchaseEvents
            )
            interaction_count = len(shop.interactionEvents)
            purchase_count = len(shop.purchaseEvents)

            billing_plan = shop.billingPlans[0] if shop.billingPlans else None

            summary.append(
                {
                    "shop_id": shop.id,
                    "shop_domain": shop.shopDomain,
                    "total_revenue": total_revenue,
                    "interaction_count": interaction_count,
                    "purchase_count": purchase_count,
                    "trial_active": (
                        billing_plan.isTrialActive if billing_plan else False
                    ),
                    "trial_revenue": billing_plan.trialRevenue if billing_plan else 0,
                    "trial_threshold": (
                        billing_plan.trialThreshold if billing_plan else 0
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
        result = await create_comprehensive_billing_test_data()
        print(f"Test data creation result: {result}")

    asyncio.run(main())
