"""
Enhanced seed pipeline runner with SQLAlchemy, user sessions, and user interactions.
"""

import asyncio
import random
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, func
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
    PipelineWatermark,
    # Additional models for cleanup
    ProductData,
    CustomerData,
    OrderData,
    LineItemData,
    CollectionData,
    UserFeatures,
    ProductFeatures,
    CollectionFeatures,
    CustomerBehaviorFeatures,
    InteractionFeatures,
    SessionFeatures,
    ProductPairFeatures,
    SearchProductFeatures,
    PurchaseAttribution,
    RefundAttribution,
    BillingPlan,
    BillingInvoice,
    BillingEvent,
    ExtensionActivity,
)


# Import our new generators
from seed_data_generators.base_generator import BaseGenerator
from seed_data_generators.product_generator import ProductGenerator
from seed_data_generators.customer_generator import CustomerGenerator
from seed_data_generators.order_generator import OrderGenerator
from seed_data_generators.event_generator import EventGenerator

# Import Kafka publisher for triggering normalization
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings


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

    async def cleanup_all_data(self, session: AsyncSession) -> None:
        """Delete all existing data from all tables before seeding."""
        print("🧹 Cleaning up existing data...")

        # Define all models to clean up in dependency order (child tables first)
        models_to_clean = [
            # Child/related tables first
            LineItemData,
            PurchaseAttribution,
            RefundAttribution,
            UserInteraction,
            UserSession,
            UserIdentityLink,
            # Feature tables
            UserFeatures,
            ProductFeatures,
            CollectionFeatures,
            CustomerBehaviorFeatures,
            InteractionFeatures,
            SessionFeatures,
            ProductPairFeatures,
            SearchProductFeatures,
            # Normalized data tables
            ProductData,
            CustomerData,
            OrderData,
            CollectionData,
            # Raw data tables
            RawProduct,
            RawCustomer,
            RawOrder,
            RawCollection,
            # Watermark tables
            PipelineWatermark,
            # Billing tables
            BillingEvent,
            BillingInvoice,
            BillingPlan,
            # Extension tables
            ExtensionActivity,
            # Core tables last
            Shop,
        ]

        deleted_counts = {}

        for model in models_to_clean:
            try:
                # Count records before deletion
                count_result = await session.execute(select(func.count(model.id)))
                count = count_result.scalar() or 0

                if count > 0:
                    # Delete all records from this table
                    await session.execute(delete(model))
                    deleted_counts[model.__tablename__] = count
                    print(f"  🗑️  Deleted {count} records from {model.__tablename__}")
                else:
                    print(f"  ✅ {model.__tablename__} already empty")

            except Exception as e:
                print(f"  ⚠️  Warning: Could not clean {model.__tablename__}: {e}")
                # Continue with other tables even if one fails

        # Flush changes
        await session.flush()

        total_deleted = sum(deleted_counts.values())
        print(
            f"✅ Cleanup complete: {total_deleted} total records deleted from {len(deleted_counts)} tables"
        )

        if deleted_counts:
            print("📊 Deleted records by table:")
            for table_name, count in sorted(deleted_counts.items()):
                print(f"  • {table_name}: {count} records")

    async def seed_normalized_data(
        self, session: AsyncSession, shop_id: str
    ) -> Dict[str, List[Any]]:
        """Seed all normalized data directly into main tables."""
        print("📊 Seeding normalized data...")

        # Generate data using generators
        products = self.product_generator.generate_products()
        customers = self.customer_generator.generate_customers()

        # Extract IDs for orders and events
        product_ids = [p["id"] for p in products]
        variant_ids = [p["variants"]["edges"][0]["node"]["id"] for p in products]
        customer_ids = [c["id"] for c in customers]

        orders = self.order_generator.generate_orders(
            customer_ids, variant_ids, product_ids
        )
        events = self.event_generator.generate_events(variant_ids, customer_ids)

        # Insert into normalized tables using SQLAlchemy
        print("  📦 Inserting products...")
        product_data_list = []
        raw_product_list = []
        for product in products:
            # Extract product ID from GraphQL ID
            product_id = (
                product["id"].split("/")[-1] if "/" in product["id"] else product["id"]
            )

            product_data = ProductData(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                product_id=product_id,
                title=product["title"],
                handle=product["handle"],
                description=product["description"],
                product_type=product["productType"],
                vendor=product["vendor"],
                tags=product["tags"],
                status="active",
                total_inventory=product["totalInventory"],
                price=float(product["variants"]["edges"][0]["node"]["price"]),
                compare_at_price=(
                    float(product["variants"]["edges"][0]["node"]["compareAtPrice"])
                    if product["variants"]["edges"][0]["node"]["compareAtPrice"]
                    else None
                ),
                inventory=product["totalInventory"],
                image_url=(
                    product["media"]["edges"][0]["node"]["image"]["url"]
                    if product["media"]["edges"]
                    else None
                ),
                image_alt=(
                    product["media"]["edges"][0]["node"]["image"]["altText"]
                    if product["media"]["edges"]
                    else None
                ),
                created_at=datetime.fromisoformat(product["createdAt"]),
                updated_at=datetime.fromisoformat(product["createdAt"]),
                online_store_url=product["onlineStoreUrl"],
                online_store_preview_url=product["onlineStorePreviewUrl"],
                seo_title=product["seo"]["title"] if product["seo"] else None,
                seo_description=(
                    product["seo"]["description"] if product["seo"] else None
                ),
                template_suffix=product["templateSuffix"],
                variants=product["variants"],
                images=product["media"],
                media=product["media"],
                options=[],
                collections=[],
                metafields={},
                extras={},
                is_active=True,
            )
            session.add(product_data)
            product_data_list.append(product_data)

        print("  👥 Inserting customers...")
        customer_data_list = []
        for customer in customers:
            # Extract customer ID from GraphQL ID
            customer_id = (
                customer["id"].split("/")[-1]
                if "/" in customer["id"]
                else customer["id"]
            )

            customer_data = CustomerData(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                customer_id=customer_id,
                email=customer["email"],
                first_name=customer["firstName"],
                last_name=customer["lastName"],
                total_spent=float(customer["totalSpent"]),
                order_count=customer["ordersCount"],
                state=customer["state"],
                verified_email=customer["verifiedEmail"],
                default_address=customer["defaultAddress"],
                created_at=datetime.fromisoformat(customer["createdAt"]),
                updated_at=datetime.fromisoformat(customer["updatedAt"]),
                tags=customer["tags"],
                extras={},
                is_active=True,
            )
            session.add(customer_data)
            customer_data_list.append(customer_data)

        print("  📋 Inserting orders...")
        order_data_list = []
        for order in orders:
            # Extract order ID from GraphQL ID
            order_id = order["id"].split("/")[-1] if "/" in order["id"] else order["id"]

            order_data = OrderData(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                order_id=order_id,
                order_name=order["name"],
                customer_email=order["email"],
                customer_id=(
                    order["customer"]["id"].split("/")[-1]
                    if "/" in order["customer"]["id"]
                    else order["customer"]["id"]
                ),
                total_amount=float(order["totalPriceSet"]["shopMoney"]["amount"]),
                subtotal_amount=float(order["subtotalPriceSet"]["shopMoney"]["amount"]),
                total_tax_amount=float(order["totalTaxSet"]["shopMoney"]["amount"]),
                total_shipping_amount=float(
                    order["totalShippingPriceSet"]["shopMoney"]["amount"]
                ),
                total_refunded_amount=float(
                    order["totalRefundedSet"]["shopMoney"]["amount"]
                ),
                total_outstanding_amount=float(
                    order["totalOutstandingSet"]["shopMoney"]["amount"]
                ),
                currency_code=order["currencyCode"],
                presentment_currency_code=order["presentmentCurrencyCode"],
                order_locale=order["customerLocale"],
                created_at=datetime.fromisoformat(order["createdAt"]),
                updated_at=datetime.fromisoformat(order["updatedAt"]),
                processed_at=datetime.fromisoformat(order["processedAt"]),
                cancelled_at=None,
                cancel_reason=None,
                tags=order["tags"],
                note=order["note"],
                confirmed=order["confirmed"],
                test=order["test"],
                extras={},
                order_date=datetime.fromisoformat(order["createdAt"]),
            )
            session.add(order_data)
            order_data_list.append(order_data)

            # Insert line items
            for line_item in order["lineItems"]["edges"]:
                line_item_data = LineItemData(
                    id=str(uuid.uuid4()),
                    order_id=order_data.id,
                    product_id=(
                        line_item["node"]["variant"]["product"]["id"].split("/")[-1]
                        if "/" in line_item["node"]["variant"]["product"]["id"]
                        else line_item["node"]["variant"]["product"]["id"]
                    ),
                    variant_id=(
                        line_item["node"]["variant"]["id"].split("/")[-1]
                        if "/" in line_item["node"]["variant"]["id"]
                        else line_item["node"]["variant"]["id"]
                    ),
                    title=line_item["node"]["title"],
                    quantity=line_item["node"]["quantity"],
                    price=float(line_item["node"]["variant"]["price"]),
                    properties={},
                )
                session.add(line_item_data)

        print("  🎯 Skipping behavioral events (using user interactions instead)...")
        raw_events = events  # Store events for later use in user interactions

        # Insert collections
        print("  📚 Inserting collections...")
        collections = self._generate_collections(product_ids)
        collection_data_list = []
        for collection in collections:
            # Extract collection ID from GraphQL ID
            collection_id = (
                collection["id"].split("/")[-1]
                if "/" in collection["id"]
                else collection["id"]
            )

            collection_data = CollectionData(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                collection_id=collection_id,
                title=collection["title"],
                handle=collection["handle"],
                description=collection["description"],
                template_suffix=collection["templateSuffix"],
                seo_title=(collection["seo"]["title"] if collection["seo"] else None),
                seo_description=(
                    collection["seo"]["description"] if collection["seo"] else None
                ),
                image_url=(collection["image"]["url"] if collection["image"] else None),
                image_alt=(
                    collection["image"]["altText"] if collection["image"] else None
                ),
                product_count=collection["productsCount"],
                is_automated=collection["isAutomated"],
                is_active=True,
                metafields={},
                extras={},
                created_at=datetime.fromisoformat(collection["createdAt"]),
                updated_at=datetime.fromisoformat(collection["updatedAt"]),
            )
            session.add(collection_data)
            collection_data_list.append(collection_data)

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

        print(f"✅ Normalized data seeding complete:")
        print(f"  • {len(product_data_list)} products")
        print(f"  • {len(customer_data_list)} customers")
        print(f"  • {len(order_data_list)} orders")
        print(f"  • {len(raw_events)} behavioral events")
        print(f"  • {len(collection_data_list)} collections")
        print(f"  • {len(identity_links)} identity links")

        return {
            "products": product_data_list,
            "customers": customer_data_list,
            "orders": order_data_list,
            "events": raw_events,
            "collections": collection_data_list,
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
                        interaction_metadata=event.get("data", {}),
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

    async def seed_purchase_attributions(
        self,
        session: AsyncSession,
        shop_id: str,
        user_sessions: List[Any],
        orders: List[Dict[str, Any]],
    ) -> List[Any]:
        """Create purchase attribution data linking sessions to orders."""
        print("🎯 Creating purchase attributions...")

        purchase_attributions = []

        # Create attributions for some orders (not all orders need attributions)
        orders_with_attributions = orders[
            : len(user_sessions)
        ]  # Match number of sessions

        for i, order in enumerate(orders_with_attributions):
            if i < len(user_sessions):
                user_session = user_sessions[i]

                # Generate realistic attribution data
                extensions = ["phoenix", "apollo", "venus", "atlas"]
                contributing_extensions = extensions[
                    : random.randint(1, 3)
                ]  # 1-3 extensions

                # Create attribution weights
                weights = [random.uniform(0.1, 0.8) for _ in contributing_extensions]
                total_weight = sum(weights)
                weights = [w / total_weight for w in weights]  # Normalize to 1.0

                attribution_weights = [
                    {"extension": ext, "weight": weight}
                    for ext, weight in zip(contributing_extensions, weights)
                ]

                # Calculate revenue attribution
                total_revenue = float(getattr(order, "total_amount", 0) or 0)
                attributed_revenue = {
                    ext: total_revenue * weight
                    for ext, weight in zip(contributing_extensions, weights)
                }

                # Generate interaction counts
                total_interactions = random.randint(5, 50)
                interactions_by_extension = {
                    ext: random.randint(
                        1, total_interactions // len(contributing_extensions)
                    )
                    for ext in contributing_extensions
                }

                purchase_attribution = PurchaseAttribution(
                    shop_id=shop_id,
                    customer_id=user_session.customer_id,
                    session_id=user_session.id,
                    order_id=str(getattr(order, "order_id", None) or f"order_{i}"),
                    contributing_extensions=contributing_extensions,
                    attribution_weights=attribution_weights,
                    total_revenue=total_revenue,
                    attributed_revenue=attributed_revenue,
                    total_interactions=total_interactions,
                    interactions_by_extension=interactions_by_extension,
                    purchase_at=datetime.utcnow(),
                    attribution_algorithm="multi_touch",
                    attribution_metadata={"source": "seed_pipeline"},
                )

                session.add(purchase_attribution)
                purchase_attributions.append(purchase_attribution)

        await session.flush()
        print(f"✅ Created {len(purchase_attributions)} purchase attributions")
        return purchase_attributions

    async def seed_refund_data(
        self,
        session: AsyncSession,
        shop_id: str,
        orders: List[Dict[str, Any]],
    ) -> Dict[str, List[Any]]:
        """Create refund data for some orders to enable negative feature computation."""
        print("🎯 Creating refund data...")

        refund_attributions = []

        # Create refunds for ~20% of orders to simulate realistic refund rates
        orders_to_refund = random.sample(orders, max(1, len(orders) // 5))

        for i, order in enumerate(orders_to_refund):
            order_id_str = str(getattr(order, "order_id", None) or f"order_{i}")
            refund_id = f"refund_{i}_{order_id_str}"
            refunded_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))

            # Create RefundAttribution (simplified single table approach)
            total_refund_amount = float(
                getattr(order, "total_amount", 0) or 0
            ) * random.uniform(0.5, 1.0)

            refund_attribution = RefundAttribution(
                shop_id=shop_id,
                customer_id=getattr(order, "customer_id", None),
                session_id=getattr(order, "session_id", None),
                order_id=order_id_str,
                refund_id=refund_id,
                refunded_at=refunded_at,
                total_refund_amount=total_refund_amount,
                currency_code=getattr(order, "currency_code", None) or "USD",
                contributing_extensions=["phoenix", "apollo", "venus"],
                attribution_weights={
                    "phoenix": 0.3,
                    "apollo": 0.4,
                    "venus": 0.2,
                    "atlas": 0.1,
                },
                total_refunded_revenue=total_refund_amount,
                attributed_refund={
                    "phoenix": total_refund_amount * 0.3,
                    "apollo": total_refund_amount * 0.4,
                    "venus": total_refund_amount * 0.2,
                    "atlas": total_refund_amount * 0.1,
                },
                total_interactions=random.randint(5, 20),
                interactions_by_extension={
                    "phoenix": random.randint(1, 5),
                    "apollo": random.randint(1, 5),
                    "venus": random.randint(1, 5),
                    "atlas": random.randint(1, 5),
                },
                attribution_algorithm="multi_touch",
                metadata={
                    "source": "seed_pipeline",
                    "refund_note": f"Refund for order {order_id_str}",
                    "refund_restock": random.choice([True, False]),
                },
            )
            session.add(refund_attribution)
            refund_attributions.append(refund_attribution)

        await session.flush()
        print(f"✅ Created {len(refund_attributions)} refund attributions")

        return {
            "refund_attributions": refund_attributions,
        }

    async def seed_search_product_features(
        self,
        session: AsyncSession,
        shop_id: str,
        products: List[Dict[str, Any]],
    ) -> List[Any]:
        """Create search product features data for search analytics."""
        print("🎯 Creating search product features...")

        search_product_features = []

        # Common search queries that would match our products
        search_queries = [
            "summer clothing",
            "tech accessories",
            "fashion items",
            "electronics",
            "hoodie",
            "t-shirt",
            "jeans",
            "sunglasses",
            "bag",
            "earbuds",
            "smart watch",
            "phone case",
            "laptop",
            "headphones",
            "shoes",
        ]

        # Create search features for each product with multiple queries
        for i, product in enumerate(products):
            # Each product gets 2-4 search queries
            product_queries = random.sample(
                search_queries, min(random.randint(2, 4), len(search_queries))
            )

            for query in product_queries:
                # Generate realistic search metrics
                impression_count = random.randint(10, 100)
                click_count = random.randint(1, impression_count)
                purchase_count = random.randint(0, click_count)

                # Calculate derived metrics
                click_through_rate = (
                    click_count / impression_count if impression_count > 0 else 0.0
                )
                conversion_rate = (
                    purchase_count / click_count if click_count > 0 else 0.0
                )
                avg_position = random.uniform(1.0, 10.0)

                search_feature = SearchProductFeatures(
                    shop_id=shop_id,
                    product_id=(
                        getattr(product, "product_id", None)
                        or product.get("id")
                        or f"product_{i}"
                    ),
                    search_query=query,
                    impression_count=impression_count,
                    click_count=click_count,
                    purchase_count=purchase_count,
                    avg_position=avg_position,
                    click_through_rate=click_through_rate,
                    conversion_rate=conversion_rate,
                    last_occurrence=datetime.utcnow()
                    - timedelta(days=random.randint(1, 30)),
                )

                session.add(search_feature)
                search_product_features.append(search_feature)

        await session.flush()
        print(f"✅ Created {len(search_product_features)} search product features")
        return search_product_features

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
            # Add missing event types from the event generator
            "upsell_viewed": "recommendation_viewed",
            "upsell_clicked": "recommendation_clicked",
            "upsell_add_to_cart": "recommendation_add_to_cart",
            "cross_sell_viewed": "recommendation_viewed",
            "cross_sell_clicked": "recommendation_clicked",
            "cross_sell_add_to_cart": "recommendation_add_to_cart",
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
            # Add missing extension types from the event generator
            "upsell_viewed": "apollo",
            "upsell_clicked": "apollo",
            "upsell_add_to_cart": "apollo",
            "cross_sell_viewed": "venus",
            "cross_sell_clicked": "venus",
            "cross_sell_add_to_cart": "venus",
        }

        interaction_type = interaction_mapping.get(event_type)
        extension_type = extension_mapping.get(event_type)

        return interaction_type, extension_type

    def _generate_collections(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        """Generate collection data."""
        collections = [
            {
                "id": self.dynamic_ids["collection_1_id"],
                "title": "Summer Essentials",
                "handle": "summer-essentials",
                "description": "Perfect for summer - clothing and accessories",
                "templateSuffix": None,
                "products": {
                    "edges": [
                        {"node": {"id": pid}} for pid in product_ids[:10]
                    ]  # First 10 products
                },
                "productsCount": 10,
                "isAutomated": False,
                "seo": {"title": None, "description": None},
                "image": None,
                "createdAt": self.base_generator.past_date(30).isoformat(),
                "updatedAt": self.base_generator.past_date(30).isoformat(),
            },
            {
                "id": self.dynamic_ids["collection_2_id"],
                "title": "Tech Gear",
                "handle": "tech-gear",
                "description": "Latest technology and electronics",
                "templateSuffix": None,
                "products": {
                    "edges": [
                        {"node": {"id": pid}} for pid in product_ids[10:]
                    ]  # Last 5 products
                },
                "productsCount": 5,
                "isAutomated": False,
                "seo": {"title": None, "description": None},
                "image": None,
                "createdAt": self.base_generator.past_date(25).isoformat(),
                "updatedAt": self.base_generator.past_date(25).isoformat(),
            },
            {
                "id": self.dynamic_ids["collection_3_id"],
                "title": "Fashion Forward",
                "handle": "fashion-forward",
                "description": "Trendy clothing and accessories",
                "templateSuffix": None,
                "products": {
                    "edges": [
                        {"node": {"id": pid}}
                        for pid in product_ids[:5] + product_ids[5:10]
                    ]  # Clothing + Accessories
                },
                "productsCount": 10,
                "isAutomated": False,
                "seo": {"title": None, "description": None},
                "image": None,
                "createdAt": self.base_generator.past_date(20).isoformat(),
                "updatedAt": self.base_generator.past_date(20).isoformat(),
            },
        ]
        return collections

    async def store_watermarks(
        self, session: AsyncSession, shop_id: str, data_types: List[str]
    ) -> None:
        """Store watermarks for each data type after raw data seeding."""
        print("💾 Storing watermarks for data types...")

        current_time = self.base_generator.now_utc()

        for data_type in data_types:
            # Check if watermark already exists
            result = await session.execute(
                select(PipelineWatermark).where(
                    (PipelineWatermark.shop_id == shop_id)
                    & (PipelineWatermark.data_type == data_type)
                )
            )
            existing_watermark = result.scalar_one_or_none()

            if existing_watermark:
                # Update existing watermark
                existing_watermark.last_collected_at = current_time
                existing_watermark.last_window_end = current_time
                existing_watermark.status = "collected"
                existing_watermark.updated_at = current_time
            else:
                # Create new watermark
                watermark = PipelineWatermark(
                    id=str(uuid.uuid4()),
                    shop_id=shop_id,
                    data_type=data_type,
                    last_collected_at=current_time,
                    last_window_end=current_time,
                    status="collected",
                    updated_at=current_time,
                )
                session.add(watermark)

        await session.flush()
        print(f"✅ Watermarks stored for {len(data_types)} data types")

    async def trigger_normalization_jobs(
        self, shop_id: str, data_types: List[str]
    ) -> None:
        """Trigger normalization jobs via Kafka for each data type."""
        print("🔄 Triggering normalization jobs via Kafka...")

        try:
            # Initialize Kafka publisher
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            current_time = self.base_generator.now_utc()

            for data_type in data_types:
                # Create normalization job event with broader time window
                # Use a 1-hour window to ensure we catch all the seeded data
                start_time = current_time - timedelta(hours=1)
                end_time = current_time + timedelta(minutes=5)

                normalization_event = {
                    "event_type": "normalize_data",
                    "data_type": data_type,
                    "format": "graphql",  # Seed data uses GraphQL format
                    "shop_id": shop_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "timestamp": current_time.isoformat(),
                    "source": "seed_pipeline",
                }

                # Publish normalization job
                message_id = await publisher.publish_normalization_event(
                    normalization_event
                )
                print(
                    f"  📤 Published normalization job for {data_type} (message_id: {message_id})"
                )

            print(f"✅ Normalization jobs triggered for {len(data_types)} data types")

        except Exception as e:
            print(f"❌ Failed to trigger normalization jobs: {e}")
            raise

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
                # Step 0: Clean up all existing data
                print("\n📊 Step 0: Cleaning up existing data...")
                await self.cleanup_all_data(session)

                # Step 1: Ensure shop exists
                print("\n📊 Step 1: Ensuring shop exists...")
                shop = await self.ensure_shop(session)
                shop_id = shop.id
                print(f"✅ Shop ready: {shop.shop_domain}")

                # Step 2: Seed normalized data
                print("\n📊 Step 2: Seeding normalized data...")
                raw_data = await self.seed_normalized_data(session, shop_id)

                # Step 3: Create user sessions and interactions
                print("\n📊 Step 3: Creating user sessions and interactions...")
                customer_ids = [
                    c["id"] for c in self.customer_generator.generate_customers()
                ]
                events = self.event_generator.generate_events(
                    [
                        p["variants"]["edges"][0]["node"]["id"]
                        for p in self.product_generator.generate_products()
                    ],
                    customer_ids,
                )
                session_data = await self.seed_user_sessions_and_interactions(
                    session, shop_id, customer_ids, events
                )

                # Step 4: Create purchase attributions
                print("\n📊 Step 4: Creating purchase attributions...")
                purchase_attributions = await self.seed_purchase_attributions(
                    session, shop_id, session_data["user_sessions"], raw_data["orders"]
                )

                # Step 5: Create refund data
                print("\n📊 Step 5: Creating refund data...")
                refund_data = await self.seed_refund_data(
                    session, shop_id, raw_data["orders"]
                )

                # Step 6: Store watermarks for data types
                print("\n📊 Step 6: Storing watermarks...")
                data_types = ["products", "customers", "orders", "collections"]
                await self.store_watermarks(session, shop_id, data_types)

                # Step 7: Trigger normalization jobs
                print("\n📊 Step 7: Triggering normalization jobs...")
                await self.trigger_normalization_jobs(shop_id, data_types)

                # Summary
                print("\n🎯 Enhanced Pipeline Summary:")
                print(f"  ✅ Data cleanup: Success")
                print(f"  ✅ Shop creation: Success")
                print(f"  ✅ Normalized data seeding: Success")
                print(f"  ✅ User sessions and interactions: Success")
                print(f"  ✅ Purchase attributions: Success")
                print(f"  ✅ Refund data: Success")
                # print(f"  ✅ Search product features: Success")
                print(f"  ✅ Watermark storage: Success")
                print(f"  ✅ Normalization job triggering: Success")
                print(f"  • {len(raw_data['products'])} products")
                print(f"  • {len(raw_data['customers'])} customers")
                print(f"  • {len(raw_data['orders'])} orders")
                print(f"  • {len(raw_data['collections'])} collections")
                print(f"  • {len(session_data['user_sessions'])} user sessions")
                print(f"  • {len(session_data['user_interactions'])} user interactions")
                print(f"  • {len(purchase_attributions)} purchase attributions")
                print(f"  • {len(refund_data['refund_data'])} refunds")
                print(f"  • {len(refund_data['refund_line_items'])} refund line items")
                print(
                    f"  • {len(refund_data['refund_attribution_adjustments'])} refund adjustments"
                )
                # print(f"  • {len(search_features)} search product features")
                print(f"  • {len(data_types)} data type watermarks stored")
                print(f"  • {len(data_types)} normalization jobs triggered")

                # Commit all changes
                await session.commit()

                print("\n🎉 Enhanced pipeline executed successfully!")
                print(
                    "🎯 Fresh normalized data, watermarks, and normalization jobs created for testing"
                )

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
