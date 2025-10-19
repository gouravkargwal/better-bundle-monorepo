#!/usr/bin/env python3
"""
Test script to verify FBT-only checkout recommendations
"""

import asyncio
import json
from app.recommandations.models import RecommendationRequest
from app.api.v1.recommendations import fetch_recommendations_logic
from app.api.v1.recommendations import RecommendationServices
from app.core.database.session import get_transaction_context
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_fbt_checkout():
    """Test FBT-only checkout recommendations"""

    # Mock the API call from your curl request
    test_request = RecommendationRequest(
        context="checkout_page",
        limit=3,
        user_id="gid://shopify/Customer/9498103742778",
        session_id="bb266626-7e4a-4361-b38e-141d55d2d08b",
        shop_domain="gk-sphere.myshopify.com",
        product_ids=["10050278228282"],
        metadata={
            "mercury_checkout": True,
            "checkout_type": "one_page",
            "checkout_step": "order_summary",
            "cart_value": 40.13,
            "cart_items": ["10050278228282"],
            "block": "checkout.order-summary.render",
        },
    )

    print("🧪 Testing FBT-only checkout recommendations...")
    print(f"Request: {test_request.model_dump()}")

    # Initialize services (this would normally be done by the FastAPI app)
    async with get_transaction_context() as db:
        # Create mock services - in real app these are injected
        services = RecommendationServices(
            # These would be properly initialized in the real app
            smart_selection=None,  # Not used for FBT-only
            executor=None,  # Not used for FBT-only
            enrichment=None,
            exclusion=None,
            analytics=None,
            cache=None,
            category=None,
            session=None,
            shop_lookup=None,
            client_id_resolver=None,
        )

        try:
            result = await fetch_recommendations_logic(test_request, services)
            print("✅ FBT checkout test completed successfully!")
            print(f"Result: {json.dumps(result, indent=2, default=str)}")

            # Verify it's using FBT
            if (
                result.get("source") == "frequently_bought_together"
                or "fbt" in result.get("source", "").lower()
            ):
                print("✅ Confirmed: Using FBT algorithm")
            else:
                print(f"⚠️  Warning: Not using FBT, source is: {result.get('source')}")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            logger.exception("FBT test failed")


if __name__ == "__main__":
    asyncio.run(test_fbt_checkout())
