"""
Billing Sync API Endpoints

Provides admin tools to sync subscription data from Shopify
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_session
from app.core.database.models import (
    ShopSubscription,
    ShopifySubscription,
    BillingCycle,
    Shop,
)
from app.domains.billing.services.shopify_usage_billing_service_v2 import (
    ShopifyUsageBillingServiceV2,
)
from app.domains.billing.repositories.billing_repository_v2 import BillingRepositoryV2
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)
router = APIRouter()


class SyncResult(BaseModel):
    """Result of syncing a single subscription"""

    shop_domain: str
    success: bool
    message: str
    cap_amount: float = None
    current_usage: float = None
    error: str = None


class BulkSyncResponse(BaseModel):
    """Response for bulk sync operation"""

    total: int
    synced: int
    skipped: int
    errors: int
    results: List[SyncResult]


@router.post("/sync-billing-cycles", response_model=BulkSyncResponse)
async def sync_billing_cycles_from_shopify(
    shop_ids: List[str],
    session: AsyncSession = Depends(get_session),
):
    """
    Sync billing cycles from Shopify for given shops

    This endpoint:
    1. Queries Shopify GraphQL API for current subscription status
    2. Fetches real cap amount and current usage from Shopify
    3. Creates billing cycles with synced data
    4. Ensures data consistency between Shopify and local database

    Args:
        shop_ids: List of shop IDs to sync

    Returns:
        Bulk sync response with results for each shop
    """
    results = []
    synced_count = 0
    skipped_count = 0
    error_count = 0

    try:
        # Initialize services
        billing_repository = BillingRepositoryV2(session)
        billing_service = ShopifyUsageBillingServiceV2(session, billing_repository)

        for shop_id in shop_ids:
            try:
                # Get shop subscription with eager loaded shop
                shop_subscription_query = (
                    select(ShopSubscription)
                    .where(
                        and_(
                            ShopSubscription.shop_id == shop_id,
                            ShopSubscription.status == "ACTIVE",
                        )
                    )
                    .options(selectinload(ShopSubscription.shop))
                )
                result = await session.execute(shop_subscription_query)
                shop_subscription = result.scalar_one_or_none()

                if not shop_subscription:
                    results.append(
                        SyncResult(
                            shop_domain=shop_id,
                            success=False,
                            message="No active subscription found",
                            error="SUBSCRIPTION_NOT_FOUND",
                        )
                    )
                    error_count += 1
                    continue

                # Check if billing cycle already exists
                existing_cycle_query = select(BillingCycle).where(
                    and_(
                        BillingCycle.shop_subscription_id == shop_subscription.id,
                        BillingCycle.status == "ACTIVE",
                    )
                )
                cycle_result = await session.execute(existing_cycle_query)
                existing_cycle = cycle_result.scalar_one_or_none()

                if existing_cycle:
                    results.append(
                        SyncResult(
                            shop_domain=shop_subscription.shop.shop_domain,
                            success=True,
                            message="Billing cycle already exists",
                        )
                    )
                    skipped_count += 1
                    continue

                # Get shop
                shop_query = select(Shop).where(Shop.id == shop_id)
                shop_result = await session.execute(shop_query)
                shop = shop_result.scalar_one_or_none()

                if not shop or not shop.access_token:
                    results.append(
                        SyncResult(
                            shop_domain=shop.shop_domain if shop else shop_id,
                            success=False,
                            message="No valid access token",
                            error="NO_ACCESS_TOKEN",
                        )
                    )
                    error_count += 1
                    continue

                # Get Shopify subscription
                shopify_sub_query = select(ShopifySubscription).where(
                    ShopifySubscription.shop_subscription_id == shop_subscription.id
                )
                shopify_sub_result = await session.execute(shopify_sub_query)
                shopify_sub = shopify_sub_result.scalar_one_or_none()

                if not shopify_sub or not shopify_sub.shopify_subscription_id:
                    results.append(
                        SyncResult(
                            shop_domain=shop.shop_domain,
                            success=False,
                            message="No Shopify subscription ID found",
                            error="NO_SHOPIFY_SUBSCRIPTION",
                        )
                    )
                    error_count += 1
                    continue

                # Fetch subscription data from Shopify
                subscription_status = await billing_service.get_subscription_status(
                    shop.shop_domain,
                    shop.access_token,
                    shopify_sub.shopify_subscription_id,
                )

                if not subscription_status:
                    raise Exception("No data returned from Shopify API")

                # Extract cap amount and usage from Shopify response
                subscription_data = subscription_status.get("subscription", {})
                line_items = subscription_data.get("lineItems", [])

                if not line_items:
                    raise Exception("No line items in Shopify subscription")

                pricing_details = (
                    line_items[0].get("plan", {}).get("pricingDetails", {})
                )
                capped_amount_data = pricing_details.get("cappedAmount", {})
                balance_used_data = pricing_details.get("balanceUsed", {})

                cap_amount = Decimal(str(capped_amount_data.get("amount", "1000")))
                current_usage = Decimal(str(balance_used_data.get("amount", "0")))

                # Create billing cycle with Shopify data
                billing_cycle = BillingCycle(
                    shop_subscription_id=shop_subscription.id,
                    cycle_number=1,
                    start_date=now_utc(),
                    end_date=now_utc() + timedelta(days=30),
                    initial_cap_amount=cap_amount,
                    current_cap_amount=cap_amount,
                    usage_amount=current_usage,
                    commission_count=0,
                    status="ACTIVE",
                    activated_at=now_utc(),
                )

                session.add(billing_cycle)
                await session.commit()

                results.append(
                    SyncResult(
                        shop_domain=shop.shop_domain,
                        success=True,
                        message=f"Synced from Shopify",
                        cap_amount=float(cap_amount),
                        current_usage=float(current_usage),
                    )
                )
                synced_count += 1

                logger.info(
                    f"✅ Synced billing cycle for {shop.shop_domain}: "
                    f"cap=${cap_amount}, usage=${current_usage}"
                )

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                logger.error(f"Error syncing shop {shop_id}: {error_msg}")

                # Try to get shop domain for error message
                try:
                    shop_query = select(Shop).where(Shop.id == shop_id)
                    shop_result = await session.execute(shop_query)
                    shop = shop_result.scalar_one_or_none()
                    shop_domain = shop.shop_domain if shop else shop_id
                except:
                    shop_domain = shop_id

                results.append(
                    SyncResult(
                        shop_domain=shop_domain,
                        success=False,
                        message="Error syncing subscription",
                        error=error_msg,
                    )
                )

                # Rollback failed transaction
                await session.rollback()

        return BulkSyncResponse(
            total=len(shop_ids),
            synced=synced_count,
            skipped=skipped_count,
            errors=error_count,
            results=results,
        )

    except Exception as e:
        logger.error(f"Fatal error in bulk sync: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/check-missing-cycles")
async def check_missing_billing_cycles(
    session: AsyncSession = Depends(get_session),
):
    """
    Check which ACTIVE subscriptions are missing billing cycles

    Returns:
        List of shop IDs that need billing cycles created
    """
    try:
        # Find ACTIVE subscriptions without billing cycles
        query = """
        SELECT ss.shop_id, s.shop_domain, ss.id as subscription_id
        FROM shop_subscriptions ss
        JOIN shops s ON s.id = ss.shop_id
        LEFT JOIN billing_cycles bc ON bc.shop_subscription_id = ss.id AND bc.status = 'ACTIVE'
        WHERE ss.status = 'ACTIVE' 
        AND ss.is_active = true
        AND bc.id IS NULL
        """

        result = await session.execute(query)
        missing = result.fetchall()

        return {
            "count": len(missing),
            "shops": [
                {
                    "shop_id": row[0],
                    "shop_domain": row[1],
                    "subscription_id": row[2],
                }
                for row in missing
            ],
        }

    except Exception as e:
        logger.error(f"Error checking missing cycles: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check missing cycles: {str(e)}"
        )
