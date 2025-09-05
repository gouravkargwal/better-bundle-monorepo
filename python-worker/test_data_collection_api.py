#!/usr/bin/env python3
"""
Test script to trigger data collection consumer via API
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_data_collection_api():
    """Test the data collection consumer API endpoints"""
    base_url = "http://localhost:8001"

    print("🚀 Testing Data Collection Consumer API...")
    print(f"📡 Base URL: {base_url}")
    print("=" * 60)

    # Test data
    shop_id = "cmf4uf3tr0000v3rsmi68lnrj"  # Your test shop ID
    shop_domain = "test-shop.myshopify.com"
    access_token = "your-access-token-here"  # Replace with actual token

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Trigger data collection consumer
        print("\n1️⃣ Testing data collection trigger...")
        try:
            response = await client.post(
                f"{base_url}/api/data-collection/trigger",
                json={
                    "shop_id": shop_id,
                    "shop_domain": shop_domain,
                    "access_token": access_token,
                    "job_type": "data_collection",
                },
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Data collection triggered successfully!")
                print(f"   Job ID: {result.get('job_id')}")
                print(f"   Event ID: {result.get('event_id')}")
                print(f"   Status: {result.get('status')}")
                print(f"   Timestamp: {result.get('timestamp')}")

                job_id = result.get("job_id")
            else:
                print(f"❌ Failed to trigger data collection: {response.status_code}")
                print(f"   Response: {response.text}")
                return

        except httpx.ConnectError:
            print(f"❌ Connection Error: Could not connect to {base_url}")
            print("   Make sure the server is running on localhost:8001")
            return
        except Exception as e:
            print(f"❌ Error: {e}")
            return

        # Test 2: Check data collection status
        print("\n2️⃣ Testing data collection status...")
        try:
            response = await client.get(
                f"{base_url}/api/data-collection/status/{shop_id}"
            )

            if response.status_code == 200:
                status = response.json()
                print("✅ Status retrieved successfully!")
                print(f"   Shop ID: {status.get('shop_id')}")
                print(f"   Consumer Status: {status.get('consumer_status')}")
                print(f"   Active Jobs: {status.get('active_jobs')}")

                jobs = status.get("jobs", {})
                if jobs:
                    print("   Active Jobs Details:")
                    for job_id, job_info in jobs.items():
                        print(
                            f"     - {job_id}: {job_info.get('status')} (Started: {job_info.get('started_at')})"
                        )
                else:
                    print("   No active jobs found")

            else:
                print(f"❌ Failed to get status: {response.status_code}")
                print(f"   Response: {response.text}")

        except Exception as e:
            print(f"❌ Error getting status: {e}")

        # Test 3: Check overall consumer status
        print("\n3️⃣ Testing overall consumer status...")
        try:
            response = await client.get(f"{base_url}/api/consumers/status")

            if response.status_code == 200:
                consumers_status = response.json()
                print("✅ Consumer status retrieved successfully!")

                for consumer_name, status in consumers_status.items():
                    print(f"   {consumer_name}: {status.get('status', 'unknown')}")

            else:
                print(f"❌ Failed to get consumer status: {response.status_code}")
                print(f"   Response: {response.text}")

        except Exception as e:
            print(f"❌ Error getting consumer status: {e}")

    print("\n" + "=" * 60)
    print("💡 Next Steps:")
    print("1. Check the application logs for data collection progress")
    print("2. Monitor the database for new data being collected")
    print("3. Check if feature computation is automatically triggered")
    print("4. Verify that behavioral events are being processed")


async def test_with_real_shop():
    """Test with a real shop (you'll need to provide real credentials)"""
    print("\n🔧 To test with a real shop, update the following in the script:")
    print("   - shop_id: Your actual shop ID")
    print("   - shop_domain: Your actual shop domain")
    print("   - access_token: Your actual Shopify access token")
    print("\n   Then uncomment the test_with_real_shop() call below")


if __name__ == "__main__":
    print("🧪 Data Collection Consumer API Test Suite")
    print("=" * 60)

    # Run the tests
    asyncio.run(test_data_collection_api())

    # Uncomment the line below to test with real shop data
    # asyncio.run(test_with_real_shop())
