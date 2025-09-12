"""
Helper script to get access tokens for development stores.
This script helps you obtain the necessary access tokens for seeding data.
"""

import os
import sys
import json
from typing import Dict, Any


def print_instructions():
    """Print instructions for getting development store access tokens."""
    print("🔑 Development Store Access Token Helper")
    print("=" * 50)
    print()
    print("To seed data into your development stores, you need access tokens.")
    print("Here's how to get them:")
    print()
    print("1. 🏪 Create Development Stores:")
    print("   - Go to your Shopify Partner Dashboard")
    print("   - Navigate to 'Development stores'")
    print("   - Create new development stores or use existing ones")
    print()
    print("2. 🔧 Install Your App:")
    print("   - For each development store, install your BetterBundle app")
    print("   - This will generate an access token")
    print()
    print("3. 📋 Get Access Tokens:")
    print("   Option A - From your app's database:")
    print("   - Check your Prisma database for the 'Shop' table")
    print("   - Look for the 'accessToken' field for each store")
    print()
    print("   Option B - From Shopify Admin API:")
    print("   - Use the Shopify CLI: shopify app info")
    print("   - Or check your app's session storage")
    print()
    print("4. ⚙️  Configure the seeder:")
    print("   - Edit 'development_stores_config.json'")
    print("   - Add your store domains and access tokens")
    print("   - Set 'enabled': true for stores you want to seed")
    print()
    print("5. 🚀 Run the seeder:")
    print("   python -m app.scripts.seed_development_stores")
    print()


def create_sample_config():
    """Create a sample configuration file."""
    sample_config = {
        "development_stores": [
            {
                "name": "My Development Store",
                "domain": "vnsaid.myshopify.com",
                "access_token": "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",
                "description": "Development store for testing products and recommendations",
                "enabled": True,
            },
        ],
        "seeding_options": {
            "create_products": True,
            "create_customers": True,
            "create_orders": True,
            "create_collections": False,
            "clear_existing_data": False,
            "batch_size": 10,
        },
        "data_customization": {
            "product_count": 15,
            "customer_count": 8,
            "order_count": 12,
            "include_behavioral_events": False,
        },
    }

    config_path = os.path.join(
        os.path.dirname(__file__), "development_stores_config.json"
    )

    if os.path.exists(config_path):
        print(f"⚠️  Configuration file already exists: {config_path}")
        print("   Please edit it manually with your store details.")
    else:
        with open(config_path, "w") as f:
            json.dump(sample_config, f, indent=2)
        print(f"✅ Created sample configuration: {config_path}")
        print("   Please edit it with your actual store details.")


def check_existing_config():
    """Check if configuration file exists and show its contents."""
    config_path = os.path.join(
        os.path.dirname(__file__), "development_stores_config.json"
    )

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            print("📋 Current Configuration:")
            print("-" * 30)

            for i, store in enumerate(config.get("development_stores", []), 1):
                status = "✅ Enabled" if store.get("enabled", False) else "❌ Disabled"
                print(f"{i}. {store.get('name', 'Unnamed Store')}")
                print(f"   Domain: {store.get('domain', 'Not set')}")
                print(
                    f"   Token: {'Set' if store.get('access_token', '').startswith('shpat_') else 'Not set'}"
                )
                print(f"   Status: {status}")
                print()
        except json.JSONDecodeError:
            print("❌ Configuration file exists but has invalid JSON")
    else:
        print("📋 No configuration file found")
        print("   Run with --create-config to create a sample configuration")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--create-config":
            create_sample_config()
        elif sys.argv[1] == "--check-config":
            check_existing_config()
        else:
            print(
                "Usage: python get_dev_store_tokens.py [--create-config|--check-config]"
            )
    else:
        print_instructions()
        print("\n" + "=" * 50)
        check_existing_config()


if __name__ == "__main__":
    main()
