#!/usr/bin/env python3
"""
Simple Trial Data Creator

Creates basic trial data without complex JSON fields.
"""

import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_simple_trial_data():
    """Create simple trial data for testing"""
    try:
        from app.core.database.simple_db_client import get_database
        
        db = await get_database()
        
        # Create test shop
        shop = await db.shop.create({
            "id": "simple-test-shop",
            "shopDomain": "simple-test.myshopify.com",
            "accessToken": "test-token-123",
            "isActive": True,
            "email": "owner@simple-test.myshopify.com",
            "currencyCode": "USD",
            "planType": "Basic",
        })
        
        logger.info(f"✅ Created shop: {shop.shopDomain}")
        
        # Create billing plan with minimal configuration
        billing_plan = await db.billingplan.create({
            "shopId": "simple-test-shop",
            "shopDomain": "simple-test.myshopify.com",
            "name": "Free Trial Plan",
            "type": "revenue_share",
            "status": "active",
            "configuration": {},  # Empty JSON object
            "effectiveFrom": datetime.utcnow(),
            "isTrialActive": True,
            "trialThreshold": 200.0,
            "trialRevenue": 0.0,
        })
        
        logger.info(f"✅ Created billing plan: {billing_plan.id}")
        
        # Create billing event with minimal data
        billing_event = await db.billingevent.create({
            "shopId": "simple-test-shop",
            "type": "plan_created",
            "data": {},  # Empty JSON object
            "metadata": {},  # Empty JSON object
            "occurredAt": datetime.utcnow(),
        })
        
        logger.info(f"✅ Created billing event: {billing_event.id}")
        
        return {
            "status": "success",
            "shop_id": shop.id,
            "plan_id": billing_plan.id,
            "event_id": billing_event.id,
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to create simple trial data: {e}")
        return {"status": "error", "error": str(e)}


async def main():
    """Main entry point"""
    logger.info("🚀 Creating simple trial data...")
    result = await create_simple_trial_data()
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
