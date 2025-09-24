"""
Enhanced seed pipeline runner with SQLAlchemy, user sessions, and user interactions.
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
from sqlalchemy.orm import selectinload

from app.core.database import get_session_factory
from app.core.database.models import (
    Shop,
    UserSession,
    UserInteraction,
    RawProduct,
    RawCustomer,
    RawOrder,
    RawCollection,
    UserIdentityLink,
)


# Import our new generators
from seed_data_generators.base_generator import BaseGenerator
from seed_data_generators.product_generator import ProductGenerator
from seed_data_generators.customer_generator import CustomerGenerator
from seed_data_generators.order_generator import OrderGenerator
from seed_data_generators.event_generator import EventGenerator


class SeedPipelineRunner:
    """Enhanced pipeline runner with SQLAlchemy, user sessions, and user interactions."""

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

    async def ensure_shop(self, session: AsyncSession) -> Shop:
        """Ensure a Shop record exists and return it."""
        # Check if shop exists
        result = await session.execute(
            select(Shop).where(Shop.shop_domain == self.shop_domain)
        )
        shop = result.scalar_one_or_none()

        if shop:
            return shop

        # Create a new shop
        shop = Shop(
            id=str(uuid.uuid4()),
            shop_domain=self.shop_domain,
            access_token=self.access_token,
            plan_type="Free",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(shop)
        await session.flush()  # Flush to get the ID
        await session.refresh(shop)
        return shop

    async def seed_raw_data(
        self, session: AsyncSession, shop_id: str
    ) -> Dict[str, List[Any]]:
        """Seed all raw data using the generators with SQLAlchemy."""
        print("📊 Seeding raw data...")

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

        # Insert into database using SQLAlchemy
        print("  📦 Inserting products...")
        raw_products = []
        for product in products:
            raw_product = RawProduct(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                payload=product,
                shopify_id=product["product"]["id"],
                extracted_at=self.base_generator.now_utc(),
                shopify_created_at=datetime.fromisoformat(
                    product["product"]["createdAt"]
                ),
                shopify_updated_at=self.base_generator.now_utc(),
            )
            session.add(raw_product)
            raw_products.append(raw_product)

        print("  👥 Inserting customers...")
        raw_customers = []
        for customer in customers:
            raw_customer = RawCustomer(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                payload=customer,
                shopify_id=customer["customer"]["id"],
                extracted_at=self.base_generator.now_utc(),
                shopify_created_at=self.base_generator.now_utc(),
                shopify_updated_at=self.base_generator.now_utc(),
            )
            session.add(raw_customer)
            raw_customers.append(raw_customer)

        print("  📋 Inserting orders...")
        raw_orders = []
        for order in orders:
            raw_order = RawOrder(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                payload=order,
                shopify_id=order["order"]["id"],
                extracted_at=self.base_generator.now_utc(),
                shopify_created_at=datetime.fromisoformat(order["order"]["createdAt"]),
                shopify_updated_at=self.base_generator.now_utc(),
            )
            session.add(raw_order)
            raw_orders.append(raw_order)

        print("  🎯 Skipping behavioral events (using user interactions instead)...")
        raw_events = events  # Store events for later use in user interactions

        # Insert collections
        print("  📚 Inserting collections...")
        collections = self._generate_collections(product_ids)
        raw_collections = []
        for collection in collections:
            raw_collection = RawCollection(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                payload=collection,
                shopify_id=collection["collection"]["id"],
                extracted_at=self.base_generator.now_utc(),
                shopify_created_at=self.base_generator.now_utc(),
                shopify_updated_at=self.base_generator.now_utc(),
            )
            session.add(raw_collection)
            raw_collections.append(raw_collection)

        # Create user identity links
        print("  🔗 Creating user identity links...")
        client_ids = list(
            set([event["clientId"] for event in events if "clientId" in event])
        )
        linked_customer_ids = customer_ids[: len(client_ids)]

        identity_links = []
        for i, client_id in enumerate(client_ids):
            if i < len(linked_customer_ids):
                identity_link = UserIdentityLink(
                    shop_id=shop_id,
                    client_id=client_id,
                    customer_id=linked_customer_ids[i],
                )
                session.add(identity_link)
                identity_links.append(identity_link)

        # Flush to ensure data is available for next steps
        await session.flush()

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

    async def seed_user_sessions_and_interactions(
        self,
        session: AsyncSession,
        shop_id: str,
        customer_ids: List[str],
        events: List[Dict[str, Any]],
    ) -> Dict[str, List[Any]]:
        """Create user sessions and interactions with realistic user journeys."""
        print("🎯 Creating user sessions and interactions...")

        # Extract client IDs from events
        client_ids = list(
            set([event["clientId"] for event in events if "clientId" in event])
        )

        user_sessions = []
        user_interactions = []

        # Create sessions for each client
        for i, client_id in enumerate(client_ids):
            customer_id = customer_ids[i] if i < len(customer_ids) else None

            # Create user session
            user_session = UserSession(
                shop_id=shop_id,
                customer_id=customer_id,
                browser_session_id=client_id,
                status="active",
                last_active=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ip_address="192.168.1.100",
                referrer="https://google.com",
                extensions_used=["phoenix", "venus", "apollo", "atlas"],
                total_interactions=0,
            )
            session.add(user_session)
            await session.flush()  # Flush to get the session ID
            user_sessions.append(user_session)

            # Create interactions for this session based on events
            session_events = [e for e in events if e.get("clientId") == client_id]
            interaction_count = 0

            for event in session_events:
                # Map event types to interaction types and extension types
                interaction_type, extension_type = self._map_event_to_interaction(event)

                if interaction_type and extension_type:
                    interaction = UserInteraction(
                        session_id=user_session.id,
                        shop_id=shop_id,
                        customer_id=customer_id,
                        extension_type=extension_type,
                        interaction_type=interaction_type,
                        interaction_metadata=event.get("metadata", {}),
                    )
                    session.add(interaction)
                    user_interactions.append(interaction)
                    interaction_count += 1

            # Update session with interaction count
            user_session.total_interactions = interaction_count

        await session.flush()

        print(f"✅ User sessions and interactions created:")
        print(f"  • {len(user_sessions)} user sessions")
        print(f"  • {len(user_interactions)} user interactions")

        return {
            "user_sessions": user_sessions,
            "user_interactions": user_interactions,
        }

    def _map_event_to_interaction(
        self, event: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """Map behavioral events to interaction types and extension types."""
        event_type = event.get("eventType", "")

        # Map to interaction types
        interaction_mapping = {
            "page_viewed": "page_viewed",
            "product_viewed": "product_viewed",
            "product_added_to_cart": "product_added_to_cart",
            "product_removed_from_cart": "product_removed_from_cart",
            "cart_viewed": "cart_viewed",
            "collection_viewed": "collection_viewed",
            "search_submitted": "search_submitted",
            "checkout_started": "checkout_started",
            "checkout_completed": "checkout_completed",
            "customer_linked": "customer_linked",
            "recommendation_viewed": "recommendation_viewed",
            "recommendation_clicked": "recommendation_clicked",
            "recommendation_add_to_cart": "recommendation_add_to_cart",
        }

        # Map to extension types based on context
        extension_mapping = {
            "page_viewed": "atlas",
            "product_viewed": "atlas",
            "product_added_to_cart": "atlas",
            "product_removed_from_cart": "atlas",
            "cart_viewed": "atlas",
            "collection_viewed": "atlas",
            "search_submitted": "atlas",
            "checkout_started": "atlas",
            "checkout_completed": "atlas",
            "customer_linked": "atlas",
            "recommendation_viewed": "phoenix",
            "recommendation_clicked": "phoenix",
            "recommendation_add_to_cart": "phoenix",
        }

        interaction_type = interaction_mapping.get(event_type)
        extension_type = extension_mapping.get(event_type)

        return interaction_type, extension_type

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

    async def run_complete_pipeline(self) -> bool:
        """Run the complete enhanced data pipeline with SQLAlchemy."""
        print("🚀 Starting enhanced seed data pipeline...")
        print(
            "🎯 This will create realistic user journeys for meaningful Gorse training data"
        )

        try:
            # Get database session factory and create session
            session_factory = await get_session_factory()
            async with session_factory() as session:
                # Step 1: Ensure shop exists
                print("\n📊 Step 1: Ensuring shop exists...")
                shop = await self.ensure_shop(session)
                shop_id = shop.id
                print(f"✅ Shop ready: {shop.shop_domain}")

                # Step 2: Seed raw data
                print("\n📊 Step 2: Seeding enhanced raw data...")
                raw_data = await self.seed_raw_data(session, shop_id)

                # Step 3: Create user sessions and interactions
                print("\n📊 Step 3: Creating user sessions and interactions...")
                customer_ids = [
                    c["customer"]["id"]
                    for c in self.customer_generator.generate_customers()
                ]
                events = self.event_generator.generate_events(
                    [
                        p["product"]["variants"]["edges"][0]["node"]["id"]
                        for p in self.product_generator.generate_products()
                    ],
                    customer_ids,
                )
                session_data = await self.seed_user_sessions_and_interactions(
                    session, shop_id, customer_ids, events
                )

                # Summary
                print("\n🎯 Simplified Pipeline Summary:")
                print(f"  ✅ Shop creation: Success")
                print(f"  ✅ Raw data seeding: Success")
                print(f"  ✅ User sessions and interactions: Success")
                print(f"  • {len(raw_data['products'])} products")
                print(f"  • {len(raw_data['customers'])} customers")
                print(f"  • {len(raw_data['orders'])} orders")
                print(f"  • {len(raw_data['collections'])} collections")
                print(f"  • {len(session_data['user_sessions'])} user sessions")
                print(f"  • {len(session_data['user_interactions'])} user interactions")

                # Commit all changes
                await session.commit()

                print("\n🎉 Simplified pipeline executed successfully!")
                print("🎯 Raw data and shop data created for testing")

                return True

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
