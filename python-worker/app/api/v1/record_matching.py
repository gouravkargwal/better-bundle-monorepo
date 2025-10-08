"""
API endpoints for matching Shopify records with database records
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.database.session import get_session_context
from app.core.database.models import (
    Shop,
    BillingPlan,
    CommissionRecord,
    BillingInvoice,
)
from app.core.logging import get_logger
from app.domains.billing.services.commission_service import CommissionService
from app.domains.billing.services.shopify_usage_billing_service import (
    ShopifyUsageBillingService,
)
from app.domains.billing.repositories.billing_repository import BillingRepository


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/record-matching", tags=["record-matching"])


@router.get("/shopify-usage-records/{shop_id}")
async def get_shopify_usage_records(
    shop_id: str,
    start_date: Optional[str] = Query(
        None, description="Start date in YYYY-MM-DD format"
    ),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    days_back: int = Query(
        30, description="Number of days back to check if no dates provided"
    ),
):
    """
    Fetch actual usage records from Shopify for a shop.
    This directly queries Shopify's GraphQL API to get real usage records.
    """
    try:
        async with get_session_context() as session:
            from app.core.database.models import Shop, BillingPlan
            from sqlalchemy import select, and_
            from datetime import datetime, timedelta

            # Set date range
            if not start_date or not end_date:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=days_back)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")

            logger.info(
                f"Fetching Shopify usage records for shop {shop_id} from {start_date} to {end_date}"
            )

            # Get shop information
            shop_stmt = select(Shop).where(Shop.id == shop_id)
            shop_result = await session.execute(shop_stmt)
            shop = shop_result.scalar_one_or_none()

            if not shop:
                raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

            if not shop.access_token:
                raise HTTPException(
                    status_code=400, detail=f"Shop {shop_id} has no access token"
                )

            # Get billing plan
            billing_plan_stmt = select(BillingPlan).where(
                and_(BillingPlan.shop_id == shop_id, BillingPlan.status == "active")
            )
            billing_plan_result = await session.execute(billing_plan_stmt)
            billing_plan = billing_plan_result.scalar_one_or_none()

            if not billing_plan:
                raise HTTPException(
                    status_code=404, detail=f"No active billing plan for shop {shop_id}"
                )

            # Initialize services
            billing_repository = BillingRepository(session)
            usage_billing_service = ShopifyUsageBillingService(
                session, billing_repository
            )

            # Fetch usage records from Shopify
            shopify_usage_records = []

            try:
                # Get subscription status to see current usage
                if billing_plan.configuration and billing_plan.configuration.get(
                    "subscription_id"
                ):
                    subscription_status = (
                        await usage_billing_service.get_subscription_status(
                            shop.shop_domain,
                            shop.access_token,
                            billing_plan.configuration["subscription_id"],
                        )
                    )

                    if subscription_status:
                        shopify_usage_records.append(
                            {
                                "type": "subscription_status",
                                "subscription_id": billing_plan.configuration[
                                    "subscription_id"
                                ],
                                "data": subscription_status,
                                "fetched_at": datetime.now().isoformat(),
                            }
                        )

                # Note: Shopify doesn't provide a direct API to fetch individual usage records
                # We can only see the current balance and subscription status
                # Individual usage records are not exposed via their API

            except Exception as e:
                logger.warning(f"Could not fetch Shopify usage records: {e}")
                shopify_usage_records.append(
                    {
                        "type": "error",
                        "error": str(e),
                        "fetched_at": datetime.now().isoformat(),
                    }
                )

            return {
                "shop_id": shop_id,
                "shop_domain": shop.domain,
                "period": {"start_date": start_date, "end_date": end_date},
                "subscription_info": {
                    "subscription_id": (
                        billing_plan.configuration.get("subscription_id")
                        if billing_plan.configuration
                        else None
                    ),
                    "subscription_status": (
                        billing_plan.configuration.get("subscription_status")
                        if billing_plan.configuration
                        else None
                    ),
                },
                "shopify_usage_records": shopify_usage_records,
                "note": "Shopify doesn't expose individual usage records via API. Only subscription status and current balance are available.",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Shopify usage records for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
