"""
Trial Data Setup Utilities

Utility functions for creating and managing trial data in the billing system.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from prisma import Json

logger = logging.getLogger(__name__)


async def create_shop_with_trial_plan(
    shop_id: str,
    shop_domain: str,
    trial_threshold: float = 200.0,
    trial_revenue: float = 0.0,
    is_trial_active: bool = True,
    access_token: str = None,
) -> Dict[str, Any]:
    """
    Create a shop with a trial billing plan in one operation.

    Args:
        shop_id: Unique shop identifier
        shop_domain: Shop domain (e.g., 'shop.myshopify.com')
        trial_threshold: Revenue threshold for trial completion (default: $200)
        trial_revenue: Current trial revenue (default: $0)
        is_trial_active: Whether trial is active (default: True)
        access_token: Shopify access token (optional)

    Returns:
        Dictionary with creation results
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Create shop record
        shop = await db.shop.create(
            {
                "id": shop_id,
                "shopDomain": shop_domain,
                "accessToken": access_token or f"test-token-{shop_id}",
                "isActive": True,
                "email": f"owner@{shop_domain}",
                "currencyCode": "USD",
                "planType": "Basic",
            }
        )

        # Create trial billing plan

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

        logger.info(f"✅ Created shop with trial plan: {shop_domain}")

        return {
            "status": "success",
            "shop_id": shop.id,
            "shop_domain": shop.shopDomain,
            "plan_id": billing_plan.id,
            "trial_threshold": trial_threshold,
            "trial_revenue": trial_revenue,
            "is_trial_active": is_trial_active,
        }

    except Exception as e:
        logger.error(f"❌ Failed to create shop with trial plan {shop_domain}: {e}")
        return {
            "status": "error",
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "error": str(e),
        }


async def update_trial_revenue(
    shop_id: str, additional_revenue: float
) -> Dict[str, Any]:
    """
    Update trial revenue for a shop.

    Args:
        shop_id: Shop identifier
        additional_revenue: Revenue to add to current trial revenue

    Returns:
        Dictionary with update results
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Get current billing plan
        billing_plan = await db.billingplan.find_first(
            where={"shopId": shop_id, "status": "active"}
        )

        if not billing_plan:
            return {
                "status": "error",
                "message": f"No active billing plan found for shop {shop_id}",
            }

        # Calculate new trial revenue
        new_trial_revenue = float(billing_plan.trialRevenue) + additional_revenue
        trial_threshold = float(billing_plan.trialThreshold)

        # Check if trial should be completed
        is_trial_active = (
            billing_plan.isTrialActive and new_trial_revenue < trial_threshold
        )

        # Update billing plan
        updated_plan = await db.billingplan.update(
            where={"id": billing_plan.id},
            data={
                "trialRevenue": new_trial_revenue,
                "isTrialActive": is_trial_active,
            },
        )

        logger.info(f"✅ Updated trial revenue for {shop_id}: ${new_trial_revenue}")

        return {
            "status": "success",
            "shop_id": shop_id,
            "trial_revenue": new_trial_revenue,
            "trial_threshold": trial_threshold,
            "is_trial_active": is_trial_active,
            "trial_completed": not is_trial_active,
        }

    except Exception as e:
        logger.error(f"❌ Failed to update trial revenue for {shop_id}: {e}")
        return {"status": "error", "shop_id": shop_id, "error": str(e)}


async def get_trial_status(shop_id: str) -> Dict[str, Any]:
    """
    Get trial status for a shop.

    Args:
        shop_id: Shop identifier

    Returns:
        Dictionary with trial status information
    """
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Get billing plan
        billing_plan = await db.billingplan.find_first(
            where={"shopId": shop_id, "status": "active"}
        )

        if not billing_plan:
            return {
                "status": "error",
                "message": f"No active billing plan found for shop {shop_id}",
            }

        trial_revenue = float(billing_plan.trialRevenue)
        trial_threshold = float(billing_plan.trialThreshold)
        remaining_revenue = max(0, trial_threshold - trial_revenue)
        trial_progress = (
            (trial_revenue / trial_threshold) * 100 if trial_threshold > 0 else 0
        )

        return {
            "status": "success",
            "shop_id": shop_id,
            "trial_revenue": trial_revenue,
            "trial_threshold": trial_threshold,
            "remaining_revenue": remaining_revenue,
            "trial_progress": trial_progress,
            "is_trial_active": billing_plan.isTrialActive,
            "trial_completed": not billing_plan.isTrialActive,
        }

    except Exception as e:
        logger.error(f"❌ Failed to get trial status for {shop_id}: {e}")
        return {"status": "error", "shop_id": shop_id, "error": str(e)}


async def create_test_scenarios() -> Dict[str, Any]:
    """
    Create various test scenarios for trial testing.

    Returns:
        Dictionary with created test scenarios
    """
    test_scenarios = [
        {
            "name": "New Trial Shop",
            "shop_id": "test-new-trial",
            "shop_domain": "new-trial.myshopify.com",
            "trial_threshold": 200.0,
            "trial_revenue": 0.0,
            "is_trial_active": True,
        },
        {
            "name": "Trial in Progress",
            "shop_id": "test-progress-trial",
            "shop_domain": "progress-trial.myshopify.com",
            "trial_threshold": 200.0,
            "trial_revenue": 150.0,
            "is_trial_active": True,
        },
        {
            "name": "Trial Completed",
            "shop_id": "test-completed-trial",
            "shop_domain": "completed-trial.myshopify.com",
            "trial_threshold": 200.0,
            "trial_revenue": 250.0,
            "is_trial_active": False,
        },
    ]

    results = []

    for scenario in test_scenarios:
        result = await create_shop_with_trial_plan(
            shop_id=scenario["shop_id"],
            shop_domain=scenario["shop_domain"],
            trial_threshold=scenario["trial_threshold"],
            trial_revenue=scenario["trial_revenue"],
            is_trial_active=scenario["is_trial_active"],
        )
        results.append({"scenario": scenario["name"], "result": result})

    return {"status": "success", "scenarios_created": len(results), "results": results}
