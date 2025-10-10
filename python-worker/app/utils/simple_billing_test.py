"""
Simple Billing Test Data Setup

This module creates simple test data for billing scenarios that works with the existing schema.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from prisma import Json

logger = logging.getLogger(__name__)


async def create_simple_billing_test_data() -> Dict[str, Any]:
    """
    Create simple test data for billing scenarios.
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        logger.info("🚀 Creating simple billing test data...")

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

        logger.info(f"✅ Created {len(results)} billing test scenarios")

        return {
            "status": "success",
            "message": "Simple billing test data created",
            "scenarios_created": len(results),
            "results": results,
            "created_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to create simple billing test data: {e}")
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

        return {
            "scenario": "Regular Shop - Active Billing",
            "status": "success",
            "shop_id": shop_id,
            "is_trial_active": False,
        }

    except Exception as e:
        return {
            "scenario": "Regular Shop - Active Billing",
            "status": "error",
            "error": str(e),
        }


async def get_simple_billing_test_summary(db) -> Dict[str, Any]:
    """Get summary of all simple billing test data"""
    try:
        # Get all test shops
        test_shop_ids = [
            "test-trial-shop",
            "test-progress-shop",
            "test-completed-trial",
            "test-regular-shop",
        ]
        test_shops = await db.shop.find_many(where={"id": {"in": test_shop_ids}})

        summary = []
        for shop in test_shops:
            # Get billing plan for this shop
            billing_plan = await db.billingplan.find_first(where={"shopId": shop.id})

            summary.append(
                {
                    "shop_id": shop.id,
                    "shop_domain": shop.shopDomain,
                    "trial_active": (
                        billing_plan.isTrialActive if billing_plan else False
                    ),
                    "trial_revenue": (
                        float(billing_plan.trialRevenue) if billing_plan else 0
                    ),
                    "trial_threshold": (
                        float(billing_plan.trialThreshold) if billing_plan else 0
                    ),
                    "trial_progress": (
                        (
                            float(billing_plan.trialRevenue)
                            / float(billing_plan.trialThreshold)
                            * 100
                        )
                        if billing_plan and billing_plan.trialThreshold > 0
                        else 0
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
        result = await create_simple_billing_test_data()
        print(f"Simple billing test data result: {result}")

    asyncio.run(main())
