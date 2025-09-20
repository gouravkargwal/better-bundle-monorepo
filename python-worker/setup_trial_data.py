#!/usr/bin/env python3
"""
Setup Trial Data Script

This script creates test shops and billing plans for testing the trial system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_test_shop(
    shop_id: str, shop_domain: str, is_active: bool = True
) -> Dict[str, Any]:
    """Create a test shop in the database"""
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Create shop record
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": shop_domain,
                "accessToken": f"test-token-{shop_id}",
                "isActive": is_active,
                "email": f"owner@{shop_domain}",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        logger.info(f"✅ Created shop: {shop_domain} (ID: {shop_id})")
        return {"shop_id": shop.id, "shop_domain": shop.shopDomain, "status": "created"}

    except Exception as e:
        logger.error(f"❌ Failed to create shop {shop_domain}: {e}")
        return {
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "status": "error",
            "error": str(e),
        }


async def create_trial_billing_plan(
    shop_id: str,
    shop_domain: str,
    trial_threshold: float = 200.0,
    trial_revenue: float = 0.0,
    is_trial_active: bool = True,
) -> Dict[str, Any]:
    """Create a trial billing plan for a shop"""
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Create billing plan
        from prisma.types import Json

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
                        "trial_threshold": trial_threshold,
                        "trial_active": is_trial_active,
                    }
                ),
                "effectiveFrom": datetime.utcnow(),
                "isTrialActive": is_trial_active,
                "trialThreshold": trial_threshold,
                "trialRevenue": trial_revenue,
            }
        )

        logger.info(
            f"✅ Created trial billing plan for {shop_domain}: {billing_plan.id}"
        )
        return {
            "plan_id": billing_plan.id,
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "trial_threshold": trial_threshold,
            "trial_revenue": trial_revenue,
            "is_trial_active": is_trial_active,
            "status": "created",
        }

    except Exception as e:
        logger.error(f"❌ Failed to create billing plan for {shop_domain}: {e}")
        return {
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "status": "error",
            "error": str(e),
        }


async def create_billing_event(
    shop_id: str,
    event_type: str = "plan_created",
    data: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create a billing event for a shop"""
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Create billing event
        billing_event = await db.billingevent.create(
            {
                "shopId": shop_id,
                "type": event_type,
                "data": Json(data or {}),
                "metadata": Json(metadata or {}),
                "occurredAt": datetime.utcnow(),
            }
        )

        logger.info(f"✅ Created billing event for {shop_id}: {billing_event.id}")
        return {
            "event_id": billing_event.id,
            "shop_id": shop_id,
            "type": event_type,
            "status": "created",
        }

    except Exception as e:
        logger.error(f"❌ Failed to create billing event for {shop_id}: {e}")
        return {"shop_id": shop_id, "status": "error", "error": str(e)}


async def setup_trial_data() -> Dict[str, Any]:
    """Setup trial data for testing"""
    try:
        logger.info("🚀 Setting up trial data...")

        # Test shops data
        test_shops = [
            {
                "shop_id": "test-shop-1",
                "shop_domain": "trial-shop-1.myshopify.com",
                "trial_threshold": 200.0,
                "trial_revenue": 0.0,
                "is_trial_active": True,
            },
            {
                "shop_id": "test-shop-2",
                "shop_domain": "trial-shop-2.myshopify.com",
                "trial_threshold": 200.0,
                "trial_revenue": 150.0,
                "is_trial_active": True,
            },
            {
                "shop_id": "test-shop-3",
                "shop_domain": "trial-shop-3.myshopify.com",
                "trial_threshold": 200.0,
                "trial_revenue": 250.0,
                "is_trial_active": False,  # Trial completed
            },
        ]

        results = {
            "shops_created": [],
            "billing_plans_created": [],
            "billing_events_created": [],
            "summary": {},
        }

        # Create shops and billing plans
        for shop_data in test_shops:
            # Create shop
            shop_result = await create_test_shop(
                shop_data["shop_id"], shop_data["shop_domain"]
            )
            results["shops_created"].append(shop_result)

            if shop_result["status"] == "created":
                # Create billing plan
                plan_result = await create_trial_billing_plan(
                    shop_data["shop_id"],
                    shop_data["shop_domain"],
                    shop_data["trial_threshold"],
                    shop_data["trial_revenue"],
                    shop_data["is_trial_active"],
                )
                results["billing_plans_created"].append(plan_result)

                # Create billing event
                event_result = await create_billing_event(
                    shop_data["shop_id"],
                    "plan_created",
                    {
                        "trial_threshold": shop_data["trial_threshold"],
                        "plan_id": plan_result.get("plan_id"),
                    },
                    {
                        "trial_type": "revenue_based",
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
                results["billing_events_created"].append(event_result)

        # Summary
        results["summary"] = {
            "total_shops": len(results["shops_created"]),
            "successful_shops": len(
                [s for s in results["shops_created"] if s["status"] == "created"]
            ),
            "total_plans": len(results["billing_plans_created"]),
            "successful_plans": len(
                [
                    p
                    for p in results["billing_plans_created"]
                    if p["status"] == "created"
                ]
            ),
            "total_events": len(results["billing_events_created"]),
            "successful_events": len(
                [
                    e
                    for e in results["billing_events_created"]
                    if e["status"] == "created"
                ]
            ),
        }

        logger.info(f"✅ Trial data setup completed!")
        logger.info(f"📊 Summary: {results['summary']}")

        return results

    except Exception as e:
        logger.error(f"❌ Failed to setup trial data: {e}")
        return {"status": "error", "error": str(e)}


async def cleanup_trial_data() -> Dict[str, Any]:
    """Cleanup trial test data"""
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Delete test shops and related data
        test_shop_ids = ["test-shop-1", "test-shop-2", "test-shop-3"]

        # Delete billing events
        await db.billingevent.delete_many(where={"shopId": {"in": test_shop_ids}})

        # Delete billing plans
        await db.billingplan.delete_many(where={"shopId": {"in": test_shop_ids}})

        # Delete shops
        await db.shop.delete_many(where={"id": {"in": test_shop_ids}})

        logger.info(f"✅ Cleaned up trial data for shops: {test_shop_ids}")
        return {"status": "success", "deleted_shops": test_shop_ids}

    except Exception as e:
        logger.error(f"❌ Failed to cleanup trial data: {e}")
        return {"status": "error", "error": str(e)}


async def main():
    """Main entry point"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        logger.info("🧹 Cleaning up trial data...")
        result = await cleanup_trial_data()
        print(f"Cleanup result: {result}")
    else:
        logger.info("🚀 Setting up trial data...")
        result = await setup_trial_data()
        print(f"Setup result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
