#!/usr/bin/env python3
"""
Test script to directly test the repository and handler without going through the webhook
"""

import sys
import asyncio
from datetime import datetime
from pydantic import TypeAdapter

sys.path.insert(0, ".")
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository
from app.webhooks.models import ShopifyBehavioralEvent


async def test_direct_save():
    """Test saving data directly through the repository and handler"""
    print("🧪 Testing direct save to database...\n")

    # Test payload
    test_payload = {
        "id": "direct-test-123",
        "timestamp": "2025-09-05T09:30:00Z",
        "name": "page_viewed",
        "customer_id": "cust-101",
        "data": {
            "url": "https://test-shop.myshopify.com/products/test-product",
            "referrer": "https://google.com",
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    }

    shop_id = "cmf4uf3tr0000v3rsmi68lnrj"

    try:
        # Test 1: Direct Pydantic validation
        print("1️⃣ Testing Pydantic validation...")
        adapter = TypeAdapter(ShopifyBehavioralEvent)
        validated_event = adapter.validate_python(test_payload)
        print(f"✅ Validation successful!")
        print(f"   Event ID: {validated_event.id}")
        print(f"   Event Name: {validated_event.name}")
        print(f"   Event Type: {type(validated_event).__name__}")
        print()

        # Test 2: Direct repository save
        print("2️⃣ Testing direct repository save...")
        repository = WebhookRepository()
        await repository.save_behavioral_event(shop_id, test_payload, validated_event)
        print("✅ Repository save successful!")
        print()

        # Test 3: Handler processing
        print("3️⃣ Testing handler processing...")
        handler = WebhookHandler(repository)
        result = await handler.process_behavioral_event(shop_id, test_payload)
        print(f"✅ Handler processing successful!")
        print(f"   Result: {result}")
        print()

        print("🎉 All direct tests passed!")

    except Exception as e:
        print(f"❌ Error during direct test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_direct_save())
