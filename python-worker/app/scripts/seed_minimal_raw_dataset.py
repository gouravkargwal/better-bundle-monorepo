import asyncio
import uuid
import sys
import os
import random
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add the python-worker directory to Python path so we can import app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
python_worker_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, python_worker_dir)

from prisma import Json

# Use the shared DB client so we reuse connection lifecycle/retries
from app.core.database.simple_db_client import get_database
from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository


# Generate unique IDs for this run
def generate_dynamic_ids():
    """Generate unique IDs for this run to avoid conflicts"""
    base_id = random.randint(10000, 99999)
    return {
        "shop_id": f"cmfb{base_id:05d}00000v3dhw8juz526",  # Keep the same format but make it unique
        "product_1_id": f"gid://shopify/Product/{base_id + 1}",
        "product_2_id": f"gid://shopify/Product/{base_id + 2}",
        "product_3_id": f"gid://shopify/Product/{base_id + 3}",
        "variant_1_id": f"gid://shopify/ProductVariant/{base_id + 1001}",
        "variant_2_id": f"gid://shopify/ProductVariant/{base_id + 1002}",
        "variant_3_id": f"gid://shopify/ProductVariant/{base_id + 1003}",
        "customer_1_id": f"gid://shopify/Customer/{base_id + 5001}",
        "customer_2_id": f"gid://shopify/Customer/{base_id + 5002}",
        "order_1_id": f"gid://shopify/Order/{base_id + 7001}",
        "order_2_id": f"gid://shopify/Order/{base_id + 7002}",
        "line_item_1_id": f"gid://shopify/LineItem/{base_id + 8001}",
        "line_item_2_id": f"gid://shopify/LineItem/{base_id + 8002}",
        "line_item_3_id": f"gid://shopify/LineItem/{base_id + 8003}",
        "collection_id": f"gid://shopify/Collection/{base_id + 3001}",
        "checkout_id": f"gid://shopify/Checkout/{base_id + 8001}",
    }


# Generate IDs for this run
DYNAMIC_IDS = generate_dynamic_ids()

# Print the generated IDs for this run
print("🎲 Generated Dynamic IDs for this run:")
for key, value in DYNAMIC_IDS.items():
    print(f"  {key}: {value}")
print()


SHOP_DOMAIN = "fashion-store.myshopify.com"
ACCESS_TOKEN = "test-access-token"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_shop(shop_domain: str, access_token: str) -> Dict[str, Any]:
    """Ensure a Shop record exists and return it."""
    db = await get_database()
    shop = await db.shop.find_unique(where={"shopDomain": shop_domain})
    if shop:
        return shop
    # Create a minimal viable Shop record
    return await db.shop.create(
        data={
            "shopDomain": shop_domain,
            "accessToken": access_token,
            "planType": "Free",
            "isActive": True,
        }
    )


async def insert_raw_products(db, shop_id: str) -> List[Dict[str, Any]]:
    """Insert three RawProduct rows with realistic Shopify-like payloads."""
    products = [
        {
            "product": {
                "id": DYNAMIC_IDS["product_1_id"],
                "title": "Unisex Hoodie",
                "handle": "unisex-hoodie",
                "productType": "Clothing",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_1_id"],
                                "title": "Grey / Small",
                                "sku": "UH-GREY-S",
                                "price": "45.00",
                                "inventoryQuantity": 10,
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["clothing", "hoodie", "unisex"],
            }
        },
        {
            "product": {
                "id": DYNAMIC_IDS["product_2_id"],
                "title": "V-Neck T-Shirt",
                "handle": "v-neck-tshirt",
                "productType": "Clothing",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_2_id"],
                                "title": "White / Medium",
                                "sku": "VT-WHT-M",
                                "price": "25.00",
                                "inventoryQuantity": 15,
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["clothing", "tshirt", "v-neck"],
            }
        },
        {
            "product": {
                "id": DYNAMIC_IDS["product_3_id"],
                "title": "Sunglasses",
                "handle": "sunglasses",
                "productType": "Accessories",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_3_id"],
                                "title": "Black",
                                "sku": "SG-BLK",
                                "price": "55.00",
                                "inventoryQuantity": 5,
                                "compareAtPrice": "75.00",
                            }
                        }
                    ]
                },
                "tags": ["accessories", "sunglasses", "black"],
            }
        },
    ]

    created = []
    for p in products:
        created.append(
            await db.rawproduct.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(p),
                    "shopifyId": p["product"]["id"],
                    "extractedAt": now_utc(),
                    "shopifyCreatedAt": now_utc(),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


async def insert_raw_customers(db, shop_id: str) -> List[Dict[str, Any]]:
    """Insert two RawCustomer rows."""
    customers = [
        {
            "customer": {
                "id": DYNAMIC_IDS["customer_1_id"],
                "email": "alice@example.com",
                "firstName": "Alice",
                "lastName": "Doe",
                "totalSpent": "90.00",
                "ordersCount": 1,
                "tags": ["vip"],
            }
        },
        {
            "customer": {
                "id": DYNAMIC_IDS["customer_2_id"],
                "email": "bob@example.com",
                "firstName": "Bob",
                "lastName": "Smith",
                "totalSpent": "80.00",
                "ordersCount": 1,
                "tags": ["new"],
            }
        },
    ]

    created = []
    for c in customers:
        created.append(
            await db.rawcustomer.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(c),
                    "shopifyId": c["customer"]["id"],
                    "extractedAt": now_utc(),
                    "shopifyCreatedAt": now_utc(),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


async def insert_raw_orders(
    db, shop_id: str, customer_ids: List[str], product_variant_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert two RawOrder rows referencing existing customers/products in payload."""
    orders = [
        {
            "order": {
                "id": DYNAMIC_IDS["order_1_id"],
                "name": "#1001",
                "email": "alice@example.com",
                "customer": {"id": customer_ids[0]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_1_id"],
                                "quantity": 2,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "45.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Unisex Hoodie - Grey / Small",
                                "variant": {"id": product_variant_ids[0]},
                            }
                        },
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_2_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "25.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "V-Neck T-Shirt - White / Medium",
                                "variant": {"id": product_variant_ids[1]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "115.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "115.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": "2025-01-08T10:00:00Z",
                "tags": ["processed"],
            }
        },
        {
            "order": {
                "id": DYNAMIC_IDS["order_2_id"],
                "name": "#1002",
                "email": "bob@example.com",
                "customer": {"id": customer_ids[1]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_2_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "55.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Sunglasses - Black",
                                "variant": {"id": product_variant_ids[2]},
                            }
                        },
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_3_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "25.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "V-Neck T-Shirt - White / Medium",
                                "variant": {"id": product_variant_ids[1]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "80.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "80.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": "2025-01-08T11:30:00Z",
                "tags": ["processed"],
            }
        },
    ]

    created = []
    for o in orders:
        created.append(
            await db.raworder.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(o),
                    "shopifyId": o["order"]["id"],
                    "extractedAt": now_utc(),
                    "shopifyCreatedAt": now_utc(),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


async def insert_raw_collection(
    db, shop_id: str, product_ids: List[str]
) -> Dict[str, Any]:
    """Insert one RawCollection referencing products in payload."""
    collection = {
        "collection": {
            "id": DYNAMIC_IDS["collection_id"],
            "title": "Summer Collection",
            "handle": "summer-collection",
            "description": "Perfect summer essentials",
            "products": {"edges": [{"node": {"id": pid}} for pid in product_ids]},
            "productCount": len(product_ids),
            "isAutomated": False,
        }
    }
    return await db.rawcollection.create(
        data={
            "shopId": shop_id,
            "payload": Json(collection),
            "shopifyId": collection["collection"]["id"],
            "extractedAt": now_utc(),
            "shopifyCreatedAt": now_utc(),
            "shopifyUpdatedAt": now_utc(),
        }
    )


def _event_payload(
    event_name: str,
    client_id: str,
    seq: int,
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": f"e_{uuid.uuid4()}",
        "name": event_name,
        "timestamp": now_utc().isoformat(),
        "clientId": client_id,
        "seq": seq,
        "type": "standard",
        "context": {
            "document": {
                "location": {
                    "href": f"https://{SHOP_DOMAIN}/",
                    "pathname": "/",
                    "search": "",
                },
                "referrer": f"https://{SHOP_DOMAIN}/",
                "title": "Fashion Store",
            },
            "shop": {
                "domain": SHOP_DOMAIN,
            },
        },
    }

    if extra:
        base.update({"data": extra})
    else:
        base.update({"data": {}})
    return base


async def insert_raw_behavioral_events(
    db, shop_id: str, product_variant_ids: List[str], customer_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert 10 RawBehavioralEvents with realistic payloads referencing variants."""
    # Customer 1 journey (Alice) - all anonymous browsing
    client1 = str(uuid.uuid4())
    alice_customer_id = customer_ids[0]  # Alice's customer ID (for linking later)
    events: List[Dict[str, Any]] = []

    # Alice's journey (Customer 1) - 7 events (all anonymous)
    # 1-2: page_viewed (browsing anonymously)
    events.append(_event_payload("page_viewed", client1, 1, {}))
    events.append(_event_payload("page_viewed", client1, 2, {}))

    # 3: product_viewed (hoodie) - still anonymous
    events.append(
        _event_payload(
            "product_viewed",
            client1,
            3,
            {
                "productVariant": {
                    "id": product_variant_ids[0],
                    "title": "Unisex Hoodie - Grey / Small",
                    "sku": "UH-GREY-S",
                    "price": {"amount": 45.0, "currencyCode": "USD"},
                }
            },
        )
    )

    # 4: product_added_to_cart (hoodie) - still anonymous
    events.append(
        _event_payload(
            "product_added_to_cart",
            client1,
            4,
            {
                "cartLine": {
                    "quantity": 2,
                    "merchandise": {
                        "id": product_variant_ids[0],
                        "title": "Unisex Hoodie - Grey / Small",
                        "sku": "UH-GREY-S",
                        "price": {"amount": 45.0, "currencyCode": "USD"},
                    },
                }
            },
        )
    )

    # 5: product_viewed (t-shirt) - still anonymous
    events.append(
        _event_payload(
            "product_viewed",
            client1,
            5,
            {
                "productVariant": {
                    "id": product_variant_ids[1],
                    "title": "V-Neck T-Shirt - White / Medium",
                    "sku": "VT-WHT-M",
                    "price": {"amount": 25.0, "currencyCode": "USD"},
                }
            },
        )
    )

    # 6: collection_viewed - still anonymous
    events.append(
        _event_payload(
            "collection_viewed",
            client1,
            6,
            {
                "collection": {
                    "id": DYNAMIC_IDS["collection_id"],
                    "title": "Summer Collection",
                }
            },
        )
    )

    # 7: checkout_completed (Alice's purchase) - still anonymous
    events.append(
        _event_payload(
            "checkout_completed",
            client1,
            7,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_id"],
                    "email": "alice@example.com",
                    "currencyCode": "USD",
                    "totalPrice": {"amount": 90.0, "currencyCode": "USD"},
                    "order": {"id": DYNAMIC_IDS["order_1_id"], "isFirstOrder": True},
                }
            },
        )
    )

    # Bob's journey (Customer 2) - all anonymous browsing
    client2 = str(uuid.uuid4())
    bob_customer_id = customer_ids[1]  # Bob's customer ID (for linking later)

    # 8: search_submitted - anonymous
    events.append(
        _event_payload(
            "search_submitted",
            client2,
            8,
            {
                "searchResult": {
                    "query": "sunglasses",
                }
            },
        )
    )

    # 9: product_viewed (sunglasses) - anonymous
    events.append(
        _event_payload(
            "product_viewed",
            client2,
            9,
            {
                "productVariant": {
                    "id": product_variant_ids[2],
                    "title": "Sunglasses - Black",
                    "sku": "SG-BLK",
                    "price": {"amount": 55.0, "currencyCode": "USD"},
                }
            },
        )
    )

    # 10: product_added_to_cart (sunglasses) - anonymous
    events.append(
        _event_payload(
            "product_added_to_cart",
            client2,
            10,
            {
                "cartLine": {
                    "quantity": 1,
                    "merchandise": {
                        "id": product_variant_ids[2],
                        "title": "Sunglasses - Black",
                        "sku": "SG-BLK",
                        "price": {"amount": 55.0, "currencyCode": "USD"},
                    },
                }
            },
        )
    )

    # 11: customer_linked event for Alice (simulates Alice logging in)
    events.append(
        _event_payload(
            "customer_linked",
            client1,
            11,
            {
                "customerId": alice_customer_id,
                "clientId": client1,
                "linkedAt": now_utc().isoformat(),
            },
        )
    )

    # 12: customer_linked event for Bob (simulates Bob logging in)
    events.append(
        _event_payload(
            "customer_linked",
            client2,
            12,
            {
                "customerId": bob_customer_id,
                "clientId": client2,
                "linkedAt": now_utc().isoformat(),
            },
        )
    )

    created = []
    for ev in events:
        created.append(
            await db.rawbehavioralevents.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(ev),
                    "receivedAt": now_utc(),
                }
            )
        )
    return created


async def insert_user_identity_links(
    db, shop_id: str, client_ids: List[str], customer_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert UserIdentityLink records to link clientId to customerId"""
    links = []

    # Link Alice's clientId to her customerId
    # This simulates Alice logging in after her anonymous browsing session
    links.append(
        await db.useridentitylink.create(
            data={
                "shopId": shop_id,
                "clientId": client_ids[0],  # Alice's clientId
                "customerId": customer_ids[0],  # Alice's customerId
            }
        )
    )

    # Link Bob's clientId to his customerId
    # This simulates Bob logging in after his anonymous browsing session
    links.append(
        await db.useridentitylink.create(
            data={
                "shopId": shop_id,
                "clientId": client_ids[1],  # Bob's clientId
                "customerId": customer_ids[1],  # Bob's customerId
            }
        )
    )

    return links


async def main():
    db = await get_database()

    # Ensure shop exists
    shop = await ensure_shop(SHOP_DOMAIN, ACCESS_TOKEN)
    shop_id = shop.id

    # Insert raw products
    raw_products = await insert_raw_products(db, shop_id)
    product_ids = [p.payload.get("product", {}).get("id") for p in raw_products]
    variant_ids = [
        p.payload.get("product", {})
        .get("variants", {})
        .get("edges", [{}])[0]
        .get("node", {})
        .get("id")
        for p in raw_products
    ]

    # Insert raw customers
    raw_customers = await insert_raw_customers(db, shop_id)
    customer_ids = [c.payload.get("customer", {}).get("id") for c in raw_customers]

    # Insert raw orders (reference customer + variants in payload)
    await insert_raw_orders(db, shop_id, customer_ids, variant_ids)

    # Insert one raw collection (reference product ids)
    await insert_raw_collection(db, shop_id, product_ids)

    # Insert behavioral events (10) with customer linking
    raw_events = await insert_raw_behavioral_events(
        db, shop_id, variant_ids, customer_ids
    )

    # Extract client IDs from the events (Alice and Bob's client IDs)
    alice_client_id = raw_events[0].payload.get("clientId")  # First event is Alice's
    bob_client_id = raw_events[7].payload.get("clientId")  # 8th event is Bob's first

    # Create UserIdentityLink records
    await insert_user_identity_links(
        db, shop_id, [alice_client_id, bob_client_id], customer_ids
    )

    print(
        "Seeding complete: 1 shop, 3 products, 2 customers, 2 orders, 1 collection, 12 events (including 2 customer_linked events), 2 identity links"
    )

    return shop_id


async def process_raw_to_main_tables(shop_id: str):
    """Process raw data to main tables"""
    print("\n🔄 Processing raw data to main tables...")

    try:
        service = MainTableStorageService()
        result = await service.store_all_data(shop_id=shop_id, incremental=True)
        print(f"✅ Main table processing completed: {result}")
        return True
    except Exception as e:
        print(f"❌ Main table processing failed: {e}")
        return False


async def process_behavioral_events(shop_id: str):
    """Process behavioral events directly using webhook handler"""
    print("\n🔄 Processing behavioral events directly...")

    try:
        # Get shop domain from shop ID
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            print(f"❌ Shop not found: {shop_id}")
            return False

        shop_domain = shop.shopDomain
        print(f"🔍 Processing events for shop domain: {shop_domain}")

        # Initialize webhook handler
        repository = WebhookRepository()
        handler = WebhookHandler(repository)

        # Get all raw behavioral events for this shop
        raw_events = await db.rawbehavioralevents.find_many(
            where={"shopId": shop_id}, order={"receivedAt": "asc"}
        )

        print(f"🔍 Found {len(raw_events)} raw behavioral events to process")

        processed_count = 0
        for raw_event in raw_events:
            try:
                # Process each event directly through the webhook handler
                result = await handler.process_behavioral_event(
                    shop_domain=shop_domain, payload=raw_event.payload
                )
                if result.get("status") == "success":
                    processed_count += 1
                    print(f"✅ Processed event: {raw_event.id}")
                else:
                    print(f"⚠️ Event processing warning: {result}")
            except Exception as e:
                print(f"❌ Failed to process event {raw_event.id}: {e}")

        print(
            f"✅ Successfully processed {processed_count}/{len(raw_events)} behavioral events"
        )

        # Verify events were saved to main table
        event_count = await db.behavioralevents.count(where={"shopId": shop_id})
        print(
            f"✅ Found {event_count} behavioral events in main table after processing"
        )

        return True
    except Exception as e:
        print(f"❌ Behavioral events processing failed: {e}")
        return False


async def compute_features(shop_id: str):
    """Compute ML features"""
    print("\n🔄 Computing ML features...")

    try:
        service = FeatureEngineeringService()
        # Get shop data first
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            print(f"❌ Shop not found: {shop_id}")
            return False

        # Convert Prisma Shop object to dictionary
        shop_dict = {
            "id": shop.id,
            "shopDomain": shop.shopDomain,
            "accessToken": shop.accessToken,
            "planType": shop.planType,
            "currencyCode": shop.currencyCode,
            "moneyFormat": shop.moneyFormat,
            "isActive": shop.isActive,
            "email": shop.email,
            "createdAt": shop.createdAt,
            "updatedAt": shop.updatedAt,
            "lastAnalysisAt": shop.lastAnalysisAt,
        }
        result = await service.run_comprehensive_pipeline_for_shop(
            shop_id=shop_id, batch_size=100, incremental=True
        )
        print(f"✅ Feature computation completed: {result}")
        return True
    except Exception as e:
        print(f"❌ Feature computation failed: {e}")
        return False


async def run_complete_pipeline():
    """Run the complete data pipeline: seed -> process -> compute features"""
    print("🚀 Starting complete data pipeline...")

    # Step 1: Seed raw data
    print("\n📊 Step 1: Seeding raw data...")
    shop_id = await main()

    # Step 2: Process raw data to main tables
    print("\n📊 Step 2: Processing raw data to main tables...")
    main_success = await process_raw_to_main_tables(shop_id)

    # Step 3: Process behavioral events
    print("\n📊 Step 3: Processing behavioral events...")
    events_success = await process_behavioral_events(shop_id)

    # Step 4: Compute ML features
    print("\n📊 Step 4: Computing ML features...")
    features_success = await compute_features(shop_id)

    # Summary
    print("\n🎯 Pipeline Summary:")
    print(f"  ✅ Raw data seeding: {'Success' if shop_id else 'Failed'}")
    print(
        f"  {'✅' if main_success else '❌'} Main table processing: {'Success' if main_success else 'Failed'}"
    )
    print(
        f"  {'✅' if events_success else '❌'} Behavioral events processing: {'Success' if events_success else 'Failed'}"
    )
    print(
        f"  {'✅' if features_success else '❌'} Feature computation: {'Success' if features_success else 'Failed'}"
    )

    if all([shop_id, main_success, events_success, features_success]):
        print("\n🎉 Complete pipeline executed successfully!")
    else:
        print("\n⚠️  Pipeline completed with some failures. Check logs above.")


if __name__ == "__main__":
    asyncio.run(run_complete_pipeline())
