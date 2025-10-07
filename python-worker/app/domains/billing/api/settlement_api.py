"""
Billing Settlement API
Runs daily to check and settle completed billing periods
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime, timedelta, date
from decimal import Decimal
import asyncio
import logging

from app.shared.helpers.datetime_utils import now_utc

from app.core.database.session import get_session_context
from app.core.database.models import (
    Shop,
    BillingPlan,
    BillingInvoice,
    PurchaseAttribution,
)
from sqlalchemy import select, and_, func
from sqlalchemy.dialects.postgresql import NUMERIC
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
logger = logging.getLogger(__name__)

# Auth
CRON_SECRET = "your-secret-key-here"  # TODO: Move to env


def verify_cron_secret(x_cron_secret: str = Header(None)):
    """Verify cron secret"""
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


class SettlementResponse(BaseModel):
    success: bool
    total_shops_checked: int
    shops_settled: int
    shops_skipped: int
    shops_failed: int
    total_revenue: float
    total_commission: float
    settlements: List[dict]
    errors: List[dict]


@router.post("/settle-daily", response_model=SettlementResponse)
async def settle_daily_periods(
    dry_run: bool = False, authorized: bool = Depends(verify_cron_secret)
):
    """
    Daily settlement check - finds and settles all shops whose
    30-day period ended yesterday.
    """

    logger.info(f"🚀 Starting daily settlement check (dry_run={dry_run})")

    settlements = []
    errors = []
    total_revenue = 0.0
    total_commission = 0.0

    async with get_session_context() as session:
        yesterday = (now_utc() - timedelta(days=1)).date()

        logger.info(f"📅 Checking for periods ending on: {yesterday}")

        # Find all active shops with subscriptions
        shops_query = (
            select(Shop, BillingPlan)
            .join(BillingPlan, Shop.id == BillingPlan.shop_id)
            .where(
                and_(
                    Shop.is_active == True,
                    BillingPlan.subscription_status == "ACTIVE",
                    BillingPlan.subscription_activated_at.isnot(None),
                )
            )
        )

        result = await session.execute(shops_query)
        shops_with_plans = result.all()

        logger.info(f"🏪 Found {len(shops_with_plans)} active shops to check")

        # Filter shops that need settlement
        shops_to_settle = []
        for shop, billing_plan in shops_with_plans:
            try:
                activation_date = billing_plan.subscription_activated_at.date()
                period_start, period_end = calculate_period_for_shop(
                    activation_date, yesterday
                )

                if period_end == yesterday:
                    shops_to_settle.append(
                        (shop, billing_plan, period_start, period_end)
                    )
                else:
                    logger.info(
                        f"⏭️ Skipping shop {shop.id} - period not ending yesterday"
                    )

            except Exception as e:
                logger.error(f"❌ Error checking shop {shop.id}: {e}")
                errors.append({"shop_id": shop.id, "error": str(e)})

        logger.info(f"🏪 Found {len(shops_to_settle)} shops ready for settlement")

        # Process settlements in parallel with concurrency control
        if shops_to_settle:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent settlements

            async def settle_shop_with_semaphore(shop_data):
                shop, billing_plan, period_start, period_end = shop_data
                async with semaphore:
                    try:
                        logger.info(
                            f"💰 Settling shop {shop.id} "
                            f"(period: {period_start} to {period_end})"
                        )

                        settlement_result = await settle_shop_period(
                            session,
                            shop,
                            billing_plan,
                            period_start,
                            period_end,
                            dry_run,
                        )

                        if settlement_result["success"]:
                            logger.info(f"✅ Successfully settled shop {shop.id}")
                            return settlement_result
                        else:
                            logger.error(
                                f"❌ Failed to settle shop {shop.id}: {settlement_result.get('error', 'unknown')}"
                            )
                            return {
                                "shop_id": shop.id,
                                "error": settlement_result.get("error", "unknown"),
                            }

                    except Exception as e:
                        logger.error(f"❌ Exception settling shop {shop.id}: {e}")
                        return {"shop_id": shop.id, "error": str(e)}

            # Execute settlements in parallel
            settlement_tasks = [
                settle_shop_with_semaphore(shop_data) for shop_data in shops_to_settle
            ]
            settlement_results = await asyncio.gather(
                *settlement_tasks, return_exceptions=True
            )

            # Process results
            for result in settlement_results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Settlement task failed: {result}")
                    errors.append({"shop_id": "unknown", "error": str(result)})
                elif result.get("success", False):
                    settlements.append(result)
                    total_revenue += result.get("net_revenue", 0)
                    total_commission += result.get("commission", 0)
                else:
                    errors.append(
                        {
                            "shop_id": result.get("shop_id", "unknown"),
                            "error": result.get("error", "unknown"),
                        }
                    )

        await session.commit()

    logger.info(
        f"✅ Settlement complete: " f"{len(settlements)} settled, {len(errors)} errors"
    )

    return SettlementResponse(
        success=True,
        total_shops_checked=len(shops_with_plans),
        shops_settled=len(settlements),
        shops_skipped=len(shops_with_plans) - len(settlements) - len(errors),
        shops_failed=len(errors),
        total_revenue=total_revenue,
        total_commission=total_commission,
        settlements=settlements,
        errors=errors,
    )


def calculate_period_for_shop(activation_date: date, check_date: date) -> tuple:
    """Calculate billing period boundaries based on shop's activation date"""

    activation_day = activation_date.day
    check_month = check_date.month
    check_year = check_date.year

    if check_date.day >= activation_day:
        period_start = date(check_year, check_month, activation_day)
    else:
        if check_month == 1:
            period_start = date(check_year - 1, 12, activation_day)
        else:
            period_start = date(check_year, check_month - 1, activation_day)

    period_end_dt = datetime.combine(period_start, datetime.min.time()) + timedelta(
        days=30
    )
    period_end = period_end_dt.date()

    return period_start, period_end


async def settle_shop_period(
    session,
    shop: Shop,
    billing_plan: BillingPlan,
    period_start: date,
    period_end: date,
    dry_run: bool = False,
) -> dict:
    """Settle a single shop's billing period with cross-period refund tracking"""

    from app.domains.billing.services.shopify_usage_billing_service import (
        ShopifyUsageBillingService,
    )
    from app.domains.billing.repositories.billing_repository import BillingRepository

    # Check if already settled
    existing_query = select(BillingInvoice).where(
        and_(
            BillingInvoice.shop_id == shop.id,
            func.date(BillingInvoice.period_start) == period_start,
            BillingInvoice.status.in_(["pending", "paid"]),
        )
    )
    existing = await session.execute(existing_query)
    if existing.scalar_one_or_none():
        logger.info(f"ℹ️ Already settled for shop {shop.id}")
        return {
            "success": True,
            "skipped": True,
            "shop_id": shop.id,
            "reason": "already_settled",
        }

    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    # ✅ Calculate purchases
    purchases_query = select(
        func.count(PurchaseAttribution.id).label("count"),
        func.coalesce(
            func.sum(
                func.cast(
                    func.jsonb_extract_path_text(
                        PurchaseAttribution.attributed_revenue, "apollo"
                    ),
                    NUMERIC,
                )
                + func.cast(
                    func.jsonb_extract_path_text(
                        PurchaseAttribution.attributed_revenue, "atlas"
                    ),
                    NUMERIC,
                )
            ),
            0,
        ).label("total"),
    ).where(
        and_(
            PurchaseAttribution.shop_id == shop.id,
            PurchaseAttribution.purchase_at >= period_start_dt,
            PurchaseAttribution.purchase_at <= period_end_dt,
        )
    )
    purchases_result = await session.execute(purchases_query)
    purchases = purchases_result.one()

    # ✅ NO REFUND COMMISSION POLICY
    # Commission is calculated on gross attributed revenue only
    # Customer refunds do not affect commission as service was delivered

    purchases_total = Decimal(str(purchases.total or 0))
    commission = purchases_total * Decimal("0.03")  # 3% of gross attributed revenue

    # Apply cap
    config = billing_plan.configuration or {}
    capped_amount = Decimal(str(config.get("capped_amount", 1000)))
    final_commission = min(commission, capped_amount)

    # Skip if zero or negative
    if final_commission <= 0:
        logger.info(f"ℹ️ Zero commission for shop {shop.id}")
        return {
            "success": True,
            "zero_charge": True,
            "shop_id": shop.id,
            "attributed_revenue": float(purchases_total),
        }

    # ✅ Create simplified description (no refund adjustments)
    period_label = period_start.strftime("%B %Y")
    description = f"Better Bundle - {period_label}\n"
    description += (
        f"Attributed Revenue: ${purchases_total:.2f} ({purchases.count} orders)\n"
    )
    description += f"Commission (3%): ${final_commission:.2f}\n"
    description += f"Note: Commission based on attributed revenue at time of purchase. Customer refunds do not affect commission as our recommendation service was successfully delivered."

    if dry_run:
        logger.info(f"🧪 DRY RUN: Would charge ${final_commission} to {shop.id}")
        return {
            "success": True,
            "dry_run": True,
            "shop_id": shop.id,
            "attributed_revenue": float(purchases_total),
            "commission": float(final_commission),
            "description": description,
        }

    # Create Shopify usage record
    logger.info(f"📤 Creating Shopify charge: ${final_commission}")

    billing_repo = BillingRepository(session)
    shopify_billing = ShopifyUsageBillingService(session, billing_repo)

    usage_record = await shopify_billing.record_usage(
        shop_id=shop.id,
        shop_domain=shop.shop_domain,
        access_token=shop.access_token,
        subscription_line_item_id=billing_plan.subscription_line_item_id,
        description=description,
        amount=final_commission,
        currency=shop.currency_code or "USD",
    )

    if not usage_record:
        logger.error(f"❌ Failed to create Shopify charge for {shop.id}")
        return {"success": False, "shop_id": shop.id, "error": "shopify_charge_failed"}

    # ✅ Create invoice with simplified metadata (no refund tracking)
    invoice_metadata = {
        "purchases_count": purchases.count,
        "attributed_revenue": float(purchases_total),
        "commission_rate": 0.03,
        "final_commission": float(final_commission),
        "capped": commission > capped_amount,
        "refund_policy": "no_commission_refunds",
        "policy_note": "Commission based on attributed revenue at time of purchase. Customer refunds do not affect commission as our recommendation service was successfully delivered.",
    }

    invoice = BillingInvoice(
        shop_id=shop.id,
        plan_id=billing_plan.id,
        invoice_number=f"BB-{shop.id[:8]}-{period_start.strftime('%Y%m%d')}",
        status="pending",
        subtotal=float(final_commission),
        taxes=0,
        discounts=0,
        total=float(final_commission),
        currency=shop.currency_code or "USD",
        period_start=period_start_dt,
        period_end=period_end_dt,
        metrics_id="",
        due_date=now_utc() + timedelta(days=30),
        shopify_charge_id=usage_record.id,
        billing_metadata=invoice_metadata,
    )

    session.add(invoice)
    await session.flush()

    logger.info(
        f"✅ Settled {shop.id}: ${final_commission} (Shopify: {usage_record.id})"
    )

    return {
        "success": True,
        "shop_id": shop.id,
        "invoice_id": invoice.id,
        "shopify_charge_id": usage_record.id,
        "attributed_revenue": float(purchases_total),
        "commission": float(final_commission),
        "period": f"{period_start} to {period_end}",
        "refund_policy": "no_commission_refunds",
    }
