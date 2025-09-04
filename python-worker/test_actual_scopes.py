#!/usr/bin/env python3
"""
Test script to get actual Shopify app scopes/permissions using GraphQL
"""

import asyncio
import httpx
import json

# GraphQL query to get actual app installation and scopes
APP_INSTALLATION_QUERY = """
query {
  currentAppInstallation {
    id
    app {
      id
      title
      developerName
    }
    accessScopes {
      handle
      description
    }
  }
}
"""

# Alternative query to get app info and scopes
APP_INFO_QUERY = """
query {
  app {
    id
    title
    developerName
    accessScopes {
      handle
      description
    }
  }
}
"""

# Query to get shop info and app installation details
SHOP_APP_QUERY = """
query {
  shop {
    id
    name
    myshopifyDomain
  }
  currentAppInstallation {
    id
    accessScopes {
      handle
      description
    }
  }
}
"""


async def test_actual_scopes(shop_domain: str, access_token: str):
    """Test to get actual app scopes from Shopify"""

    url = f"https://{shop_domain}/admin/api/2024-01/graphql.json"

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    print(f"🔍 Getting actual app scopes for: {shop_domain}")
    print(f"📡 GraphQL Endpoint: {url}")
    print(f"🔑 Access Token: {access_token[:20]}...")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:

        # Test 1: Current App Installation
        print("1️⃣ Testing Current App Installation Query...")
        try:
            response = await client.post(
                url, headers=headers, json={"query": APP_INSTALLATION_QUERY}
            )

            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print(f"   ⚠️  GraphQL Errors:")
                    for error in data["errors"]:
                        print(f"      - {error.get('message', 'Unknown error')}")
                else:
                    print(f"   ✅ Success!")
                    print(f"   📋 Response: {json.dumps(data, indent=2)}")

                    if "data" in data and "currentAppInstallation" in data["data"]:
                        installation = data["data"]["currentAppInstallation"]
                        app = installation.get("app", {})
                        scopes = installation.get("accessScopes", [])

                        print(f"\n   📱 App Info:")
                        print(f"      - ID: {app.get('id', 'N/A')}")
                        print(f"      - Title: {app.get('title', 'N/A')}")
                        print(f"      - Developer: {app.get('developerName', 'N/A')}")

                        print(f"\n   🔑 Granted Scopes ({len(scopes)} total):")
                        for i, scope in enumerate(scopes, 1):
                            print(
                                f"      {i}. {scope.get('handle', 'N/A')} - {scope.get('description', 'No description')}"
                            )

                        # Extract scope handles
                        scope_handles = [scope["handle"] for scope in scopes]
                        return scope_handles
                    else:
                        print(f"   ⚠️  No app installation data found")
            else:
                print(f"   ❌ Failed: {response.text}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

        # Test 2: App Info Query (alternative)
        print("2️⃣ Testing App Info Query (Alternative)...")
        try:
            response = await client.post(
                url, headers=headers, json={"query": APP_INFO_QUERY}
            )

            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print(f"   ⚠️  GraphQL Errors:")
                    for error in data["errors"]:
                        print(f"      - {error.get('message', 'Unknown error')}")
                else:
                    print(f"   ✅ Success!")
                    print(f"   📋 Response: {json.dumps(data, indent=2)}")

                    if "data" in data and "app" in data["data"]:
                        app = data["data"]["app"]
                        scopes = app.get("accessScopes", [])

                        print(f"\n   📱 App Info:")
                        print(f"      - ID: {app.get('id', 'N/A')}")
                        print(f"      - Title: {app.get('title', 'N/A')}")
                        print(f"      - Developer: {app.get('developerName', 'N/A')}")

                        print(f"\n   🔑 App Scopes ({len(scopes)} total):")
                        for i, scope in enumerate(scopes, 1):
                            print(
                                f"      {i}. {scope.get('handle', 'N/A')} - {scope.get('description', 'No description')}"
                            )

                        # Extract scope handles
                        scope_handles = [scope["handle"] for scope in scopes]
                        return scope_handles
                    else:
                        print(f"   ⚠️  No app data found")
            else:
                print(f"   ❌ Failed: {response.text}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

        # Test 3: Shop + App Installation
        print("3️⃣ Testing Shop + App Installation Query...")
        try:
            response = await client.post(
                url, headers=headers, json={"query": SHOP_APP_QUERY}
            )

            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print(f"   ⚠️  GraphQL Errors:")
                    for error in data["errors"]:
                        print(f"      - {error.get('message', 'Unknown error')}")
                else:
                    print(f"   ✅ Success!")
                    print(f"   📋 Response: {json.dumps(data, indent=2)}")

                    if "data" in data:
                        shop = data["data"].get("shop", {})
                        installation = data["data"].get("currentAppInstallation", {})
                        scopes = installation.get("accessScopes", [])

                        print(f"\n   🏪 Shop Info:")
                        print(f"      - ID: {shop.get('id', 'N/A')}")
                        print(f"      - Name: {shop.get('name', 'N/A')}")
                        print(f"      - Domain: {shop.get('myshopifyDomain', 'N/A')}")

                        print(f"\n   🔑 Installation Scopes ({len(scopes)} total):")
                        for i, scope in enumerate(scopes, 1):
                            print(
                                f"      {i}. {scope.get('handle', 'N/A')} - {scope.get('description', 'No description')}"
                            )

                        # Extract scope handles
                        scope_handles = [scope["handle"] for scope in scopes]
                        return scope_handles
                    else:
                        print(f"   ⚠️  No data found")
            else:
                print(f"   ❌ Failed: {response.text}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        return []


async def main():
    """Main test function"""
    print("🚀 Shopify Actual App Scopes Test")
    print("=" * 60)

    shop_domain = "vnsaid.myshopify.com"
    access_token = "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"

    # Get actual scopes
    scopes = await test_actual_scopes(shop_domain, access_token)

    if scopes:
        print(f"\n🎯 Final Results:")
        print(f"   📋 Total Scopes Found: {len(scopes)}")
        print(f"   🔑 Scope Handles: {scopes}")

        # Check for specific scopes we need
        required_scopes = [
            "read_products",
            "read_orders",
            "read_customers",
            "read_collections",
            "read_marketing_events",
        ]

        print(f"\n📊 Scope Analysis:")
        for scope in required_scopes:
            if scope in scopes:
                print(f"   ✅ {scope} - GRANTED")
            else:
                print(f"   ❌ {scope} - NOT GRANTED")

        # Determine permissions
        permissions = {
            "products": "read_products" in scopes,
            "orders": "read_orders" in scopes,
            "customers": "read_customers" in scopes,
            "collections": "read_collections" in scopes,
            "customer_events": "read_marketing_events" in scopes,
        }

        print(f"\n🎯 Permission Summary: {permissions}")

        if permissions.get("collections"):
            print("✅ Collections access is available!")
        else:
            print("❌ Collections access is NOT available")

        if permissions.get("customer_events"):
            print("✅ Customer events access is available!")
        else:
            print("❌ Customer events access is NOT available")

    print("\n" + "=" * 60)
    print("✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
