"""
Main pipeline runner for the enhanced seed data generation.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from prisma import Json
from app.core.database.simple_db_client import get_database
from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository
from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline
from app.domains.ml.services.gorse_training_service import GorseTrainingService

# Import our new generators
from seed_data_generators.base_generator import BaseGenerator
from seed_data_generators.product_generator import ProductGenerator
from seed_data_generators.customer_generator import CustomerGenerator
from seed_data_generators.order_generator import OrderGenerator
from seed_data_generators.event_generator import EventGenerator


class SeedPipelineRunner:
    """Main pipeline runner for enhanced seed data generation."""

    def __init__(
        self,
        shop_domain: str = "fashion-store.myshopify.com",
        access_token: str = "test-access-token",
    ):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.base_generator = BaseGenerator(shop_domain)
        self.product_generator = ProductGenerator(shop_domain)
        self.customer_generator = CustomerGenerator(shop_domain)
        self.order_generator = OrderGenerator(shop_domain)
        self.event_generator = EventGenerator(shop_domain)

        # Use the same dynamic IDs across all generators
        self.dynamic_ids = self.base_generator.dynamic_ids

        print("🎲 Generated Dynamic IDs for this run:")
        for key, value in sorted(self.dynamic_ids.items()):
            print(f"  {key}: {value}")
        print()

    async def ensure_shop(self) -> Dict[str, Any]:
        """Ensure a Shop record exists and return it."""
        db = await get_database()
        shop = await db.shop.find_unique(where={"shopDomain": self.shop_domain})
        if shop:
            return shop

        # Create a minimal viable Shop record
        return await db.shop.create(
            data={
                "shopDomain": self.shop_domain,
                "accessToken": self.access_token,
                "planType": "Free",
                "isActive": True,
            }
        )

    async def seed_raw_data(self, shop_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Seed all raw data using the generators."""
        print("📊 Seeding raw data...")
        db = await get_database()

        # Generate data using generators
        products = self.product_generator.generate_products()
        customers = self.customer_generator.generate_customers()

        # Extract IDs for orders and events
        product_ids = [p["product"]["id"] for p in products]
        variant_ids = [
            p["product"]["variants"]["edges"][0]["node"]["id"] for p in products
        ]
        customer_ids = [c["customer"]["id"] for c in customers]

        orders = self.order_generator.generate_orders(customer_ids, variant_ids)
        events = self.event_generator.generate_events(variant_ids, customer_ids)

        # Insert into database
        print("  📦 Inserting products...")
        raw_products = []
        for product in products:
            raw_products.append(
                await db.rawproduct.create(
                    data={
                        "shopId": shop_id,
                        "payload": Json(product),
                        "shopifyId": product["product"]["id"],
                        "extractedAt": self.base_generator.now_utc(),
                        "shopifyCreatedAt": datetime.fromisoformat(
                            product["product"]["createdAt"]
                        ),
                        "shopifyUpdatedAt": self.base_generator.now_utc(),
                    }
                )
            )

        print("  👥 Inserting customers...")
        raw_customers = []
        for customer in customers:
            raw_customers.append(
                await db.rawcustomer.create(
                    data={
                        "shopId": shop_id,
                        "payload": Json(customer),
                        "shopifyId": customer["customer"]["id"],
                        "extractedAt": self.base_generator.now_utc(),
                        "shopifyCreatedAt": self.base_generator.now_utc(),
                        "shopifyUpdatedAt": self.base_generator.now_utc(),
                    }
                )
            )

        print("  📋 Inserting orders...")
        raw_orders = []
        for order in orders:
            raw_orders.append(
                await db.raworder.create(
                    data={
                        "shopId": shop_id,
                        "payload": Json(order),
                        "shopifyId": order["order"]["id"],
                        "extractedAt": self.base_generator.now_utc(),
                        "shopifyCreatedAt": datetime.fromisoformat(
                            order["order"]["createdAt"]
                        ),
                        "shopifyUpdatedAt": self.base_generator.now_utc(),
                    }
                )
            )

        print("  🎯 Inserting behavioral events...")
        raw_events = []
        for event in events:
            raw_events.append(
                await db.rawbehavioralevents.create(
                    data={
                        "shopId": shop_id,
                        "payload": Json(event),
                        "receivedAt": datetime.fromisoformat(event["timestamp"]),
                    }
                )
            )

        # Insert collections
        print("  📚 Inserting collections...")
        collections = self._generate_collections(product_ids)
        raw_collections = []
        for collection in collections:
            raw_collections.append(
                await db.rawcollection.create(
                    data={
                        "shopId": shop_id,
                        "payload": Json(collection),
                        "shopifyId": collection["collection"]["id"],
                        "extractedAt": self.base_generator.now_utc(),
                        "shopifyCreatedAt": self.base_generator.now_utc(),
                        "shopifyUpdatedAt": self.base_generator.now_utc(),
                    }
                )
            )

        # Create user identity links
        print("  🔗 Creating user identity links...")
        client_ids = list(
            set([event["clientId"] for event in events if "clientId" in event])
        )
        linked_customer_ids = customer_ids[: len(client_ids)]

        identity_links = []
        for i, client_id in enumerate(client_ids):
            if i < len(linked_customer_ids):
                identity_links.append(
                    await db.useridentitylink.create(
                        data={
                            "shopId": shop_id,
                            "clientId": client_id,
                            "customerId": linked_customer_ids[i],
                        }
                    )
                )

        print(f"✅ Raw data seeding complete:")
        print(f"  • {len(raw_products)} products")
        print(f"  • {len(raw_customers)} customers")
        print(f"  • {len(raw_orders)} orders")
        print(f"  • {len(raw_events)} behavioral events")
        print(f"  • {len(raw_collections)} collections")
        print(f"  • {len(identity_links)} identity links")

        return {
            "products": raw_products,
            "customers": raw_customers,
            "orders": raw_orders,
            "events": raw_events,
            "collections": raw_collections,
            "identity_links": identity_links,
        }

    def _generate_collections(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        """Generate collection data."""
        collections = [
            {
                "collection": {
                    "id": self.dynamic_ids["collection_1_id"],
                    "title": "Summer Essentials",
                    "handle": "summer-essentials",
                    "description": "Perfect for summer - clothing and accessories",
                    "products": {
                        "edges": [
                            {"node": {"id": pid}} for pid in product_ids[:10]
                        ]  # First 10 products
                    },
                    "productCount": 10,
                    "isAutomated": False,
                }
            },
            {
                "collection": {
                    "id": self.dynamic_ids["collection_2_id"],
                    "title": "Tech Gear",
                    "handle": "tech-gear",
                    "description": "Latest technology and electronics",
                    "products": {
                        "edges": [
                            {"node": {"id": pid}} for pid in product_ids[10:]
                        ]  # Last 5 products
                    },
                    "productCount": 5,
                    "isAutomated": False,
                }
            },
            {
                "collection": {
                    "id": self.dynamic_ids["collection_3_id"],
                    "title": "Fashion Forward",
                    "handle": "fashion-forward",
                    "description": "Trendy clothing and accessories",
                    "products": {
                        "edges": [
                            {"node": {"id": pid}}
                            for pid in product_ids[:5] + product_ids[5:10]
                        ]  # Clothing + Accessories
                    },
                    "productCount": 10,
                    "isAutomated": False,
                }
            },
        ]
        return collections

    async def process_raw_to_main_tables(self, shop_id: str) -> bool:
        """Process raw data to main tables."""
        print("\n🔄 Processing raw data to main tables...")

        try:
            service = MainTableStorageService()
            result = await service.store_all_data(shop_id=shop_id, incremental=True)
            print(f"✅ Main table processing completed: {result}")
            return True
        except Exception as e:
            print(f"❌ Main table processing failed: {e}")
            return False

    async def process_behavioral_events(self, shop_id: str) -> bool:
        """Process behavioral events using webhook handler."""
        print("\n🔄 Processing behavioral events...")

        try:
            db = await get_database()
            shop = await db.shop.find_unique(where={"id": shop_id})
            if not shop:
                print(f"❌ Shop not found: {shop_id}")
                return False

            repository = WebhookRepository()
            handler = WebhookHandler(repository)

            raw_events = await db.rawbehavioralevents.find_many(
                where={"shopId": shop_id}, order={"receivedAt": "asc"}
            )

            print(f"🔍 Found {len(raw_events)} raw behavioral events to process")

            processed_count = 0
            for raw_event in raw_events:
                try:
                    result = await handler.process_behavioral_event(
                        shop_domain=shop.shopDomain, payload=raw_event.payload
                    )
                    if result.get("status") == "success":
                        processed_count += 1
                except Exception as e:
                    print(f"❌ Failed to process event {raw_event.id}: {e}")

            print(
                f"✅ Successfully processed {processed_count}/{len(raw_events)} behavioral events"
            )

            event_count = await db.behavioralevents.count(where={"shopId": shop_id})
            print(
                f"✅ Found {event_count} behavioral events in main table after processing"
            )

            return True
        except Exception as e:
            print(f"❌ Behavioral events processing failed: {e}")
            return False

    async def compute_features(self, shop_id: str) -> bool:
        """Compute ML features."""
        print("\n🔄 Computing ML features...")

        try:
            service = FeatureEngineeringService()
            db = await get_database()
            shop = await db.shop.find_unique(where={"id": shop_id})
            if not shop:
                print(f"❌ Shop not found: {shop_id}")
                return False

            result = await service.run_comprehensive_pipeline_for_shop(
                shop_id=shop_id, batch_size=100, incremental=True
            )
            print(f"✅ Feature computation completed: {result}")
            return True
        except Exception as e:
            print(f"❌ Feature computation failed: {e}")
            return False

    async def sync_to_gorse(self, shop_id: str) -> bool:
        """Sync feature data to Gorse."""
        print("\n🔄 Syncing data to Gorse...")

        try:
            sync_pipeline = GorseSyncPipeline()

            print("📊 Syncing users, items, and feedback to Gorse bridge tables...")
            sync_result = await sync_pipeline.sync_all(shop_id, incremental=False)

            if sync_result:
                print("✅ Gorse sync pipeline completed successfully")

                training_service = GorseTrainingService()

                print("🚀 Pushing data to Gorse and triggering training...")
                training_job_id = await training_service.push_data_to_gorse(
                    shop_id=shop_id,
                    job_type="full_training",
                    trigger_source="enhanced_seed_script",
                )

                print(f"✅ Gorse training job started: {training_job_id}")
                return True
            else:
                print("❌ Gorse sync pipeline failed")
                return False

        except Exception as e:
            print(f"❌ Gorse sync failed: {e}")
            return False

    async def test_recommendations_api(self, shop_id: str) -> bool:
        """Test the recommendations API with seeded data."""
        print("\n🔄 Testing recommendations API...")

        try:
            db = await get_database()
            customer = await db.customerdata.find_first(where={"shopId": shop_id})

            if not customer:
                print("❌ No customers found for recommendations testing")
                return False

            customer_id = customer.customerId
            print(f"🧪 Testing recommendations for customer: {customer_id}")

            from app.shared.gorse_api_client import GorseApiClient

            gorse_client = GorseApiClient(base_url="http://localhost:8088")

            # Test user recommendations
            print("📊 Testing user recommendations...")
            user_recs = await gorse_client.get_recommendations(
                user_id=f"shop_{shop_id}_{customer_id}", n=5
            )

            if user_recs.get("success") and user_recs.get("recommendations"):
                recommendations = user_recs["recommendations"]
                print(f"✅ User recommendations: {len(recommendations)} items")
                for i, rec in enumerate(recommendations[:3], 1):
                    print(
                        f"  {i}. Item: {rec.get('item_id', 'N/A')}, Score: {rec.get('score', 'N/A')}"
                    )
            else:
                print("⚠️ No user recommendations available")
                if user_recs.get("error"):
                    print(f"   Error: {user_recs['error']}")

            # Test item recommendations
            print("📊 Testing item recommendations...")
            product = await db.productdata.find_first(where={"shopId": shop_id})

            if product:
                product_id = product.productId
                item_recs = await gorse_client.get_item_neighbors(
                    item_id=f"shop_{shop_id}_{product_id}", n=5
                )

                if item_recs.get("success") and item_recs.get("neighbors"):
                    neighbors = item_recs["neighbors"]
                    print(f"✅ Item recommendations: {len(neighbors)} items")
                    for i, rec in enumerate(neighbors[:3], 1):
                        print(
                            f"  {i}. Item: {rec.get('item_id', 'N/A')}, Score: {rec.get('score', 'N/A')}"
                        )
                else:
                    print("⚠️ No item recommendations available")
                    if item_recs.get("error"):
                        print(f"   Error: {item_recs['error']}")

            print("✅ Recommendations API testing completed")
            return True

        except Exception as e:
            print(f"❌ Recommendations API testing failed: {e}")
            return False

    async def run_complete_pipeline(self) -> bool:
        """Run the complete enhanced data pipeline."""
        print("🚀 Starting enhanced seed data pipeline...")
        print(
            "🎯 This will create realistic user journeys for meaningful Gorse training data"
        )

        try:
            # Step 1: Ensure shop exists
            print("\n📊 Step 1: Ensuring shop exists...")
            shop = await self.ensure_shop()
            shop_id = shop.id
            print(f"✅ Shop ready: {shop.shopDomain}")

            # Step 2: Seed raw data
            print("\n📊 Step 2: Seeding enhanced raw data...")
            raw_data = await self.seed_raw_data(shop_id)

            # Step 3: Process raw data to main tables
            print("\n📊 Step 3: Processing raw data to main tables...")
            main_success = await self.process_raw_to_main_tables(shop_id)

            # Step 4: Process behavioral events
            print("\n📊 Step 4: Processing behavioral events...")
            events_success = await self.process_behavioral_events(shop_id)

            # Step 5: Compute ML features
            print("\n📊 Step 5: Computing ML features...")
            features_success = await self.compute_features(shop_id)

            # Step 6: Sync to Gorse
            print("\n📊 Step 6: Syncing to Gorse...")
            gorse_success = await self.sync_to_gorse(shop_id)

            # Step 7: Test recommendations
            print("\n📊 Step 7: Testing recommendations API...")
            api_success = await self.test_recommendations_api(shop_id)

            # Summary
            print("\n🎯 Enhanced Pipeline Summary:")
            print(f"  ✅ Raw data seeding: Success")
            print(
                f"  {'✅' if main_success else '❌'} Main table processing: {'Success' if main_success else 'Failed'}"
            )
            print(
                f"  {'✅' if events_success else '❌'} Behavioral events processing: {'Success' if events_success else 'Failed'}"
            )
            print(
                f"  {'✅' if features_success else '❌'} Feature computation: {'Success' if features_success else 'Failed'}"
            )
            print(
                f"  {'✅' if gorse_success else '❌'} Gorse sync: {'Success' if gorse_success else 'Failed'}"
            )
            print(
                f"  {'✅' if api_success else '❌'} API testing: {'Success' if api_success else 'Failed'}"
            )

            if all([main_success, events_success, features_success, gorse_success]):
                print("\n🎉 Enhanced pipeline executed successfully!")
                print("🎯 Realistic user journeys created with:")
                print("  • 15 diverse products across 3 categories")
                print("  • 8 customer profiles with different behaviors")
                print("  • 12 orders showing realistic purchase patterns")
                print("  • 100+ behavioral events covering complete user journeys")
                print(
                    "  • Cross-category recommendations and frequently bought together patterns"
                )
                print("  • Abandoned cart scenarios and new customer cold-start data")
                print("  • VIP customer loyalty patterns and bargain hunter behaviors")
                print(
                    "\n🚀 Gorse now has rich, realistic data for meaningful recommendations!"
                )
            else:
                print("\n⚠️ Pipeline completed with some failures. Check logs above.")

            return all([main_success, events_success, features_success, gorse_success])

        except Exception as e:
            print(f"❌ Pipeline failed with error: {e}")
            return False


async def main():
    """Main entry point."""
    runner = SeedPipelineRunner()
    success = await runner.run_complete_pipeline()
    return success


if __name__ == "__main__":
    asyncio.run(main())
