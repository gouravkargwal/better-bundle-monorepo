#!/usr/bin/env python3
"""
Seed Test Shops - Insert test shop records for the generated data
"""

import asyncio
from typing import List, Dict, Any

from app.core.database import get_database, close_database
from app.core.logging import get_logger

logger = get_logger(__name__)


async def seed_test_shops() -> Dict[str, Any]:
    """Insert test shops that match the generated data"""
    
    test_shops = [
        {
            "id": "shop_123",
            "shopDomain": "fashion-store.myshopify.com",
            "accessToken": "test_token_fashion_store_123",
            "planType": "Basic",
            "currencyCode": "USD",
            "moneyFormat": "${{amount}}",
            "isActive": True,
            "email": "admin@fashion-store.com",
        },
        {
            "id": "shop_456", 
            "shopDomain": "electronics-hub.myshopify.com",
            "accessToken": "test_token_electronics_hub_456",
            "planType": "Pro",
            "currencyCode": "USD",
            "moneyFormat": "${{amount}}",
            "isActive": True,
            "email": "admin@electronics-hub.com",
        },
        {
            "id": "shop_789",
            "shopDomain": "home-garden.myshopify.com", 
            "accessToken": "test_token_home_garden_789",
            "planType": "Basic",
            "currencyCode": "USD",
            "moneyFormat": "${{amount}}",
            "isActive": True,
            "email": "admin@home-garden.com",
        },
    ]
    
    try:
        db = await get_database()
        
        # Try to create all shops, skip duplicates
        try:
            await db.shop.create_many(data=test_shops, skip_duplicates=True)
            inserted_count = len(test_shops)
            logger.info(f"Created {len(test_shops)} test shops (skipped duplicates)")
        except Exception as e:
            logger.error(f"Failed to create shops: {str(e)}")
            # Fallback: try individual creates
            inserted_count = 0
            for shop_data in test_shops:
                try:
                    await db.shop.create(data=shop_data)
                    inserted_count += 1
                    logger.info(f"Created shop: {shop_data['id']} - {shop_data['shopDomain']}")
                except Exception as create_error:
                    logger.warning(f"Shop {shop_data['id']} might already exist: {str(create_error)}")
                    continue
        
        await close_database()
        
        return {
            "success": True,
            "inserted_count": inserted_count,
            "total_shops": len(test_shops)
        }
        
    except Exception as e:
        logger.error(f"Failed to seed test shops: {str(e)}")
        await close_database()
        return {
            "success": False,
            "error": str(e),
            "inserted_count": 0
        }


async def main():
    """Main function"""
    logger.info("Starting test shops seeding...")
    
    result = await seed_test_shops()
    
    if result["success"]:
        logger.info(f"✅ Successfully seeded {result['inserted_count']}/{result['total_shops']} test shops")
    else:
        logger.error(f"❌ Failed to seed test shops: {result.get('error')}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
