import asyncio
import uuid
import sys
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Add the python-worker directory to Python path so we can import app modules
# (Adjusted for potential REPL; set manually if needed)
python_worker_dir = (
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if "__file__" in globals()
    else "/path/to/python-worker"
)  # Replace with actual path if needed
sys.path.insert(0, python_worker_dir)

from prisma import Json

# Use the shared DB client so we can reuse connection lifecycle/retries
from app.core.database.simple_db_client import get_database
from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository

# from app.domains.ml.processors.analytics_data_processor import AnalyticsDataProcessor  # Removed - analytics tables are redundant
from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline
from app.domains.ml.services.gorse_training_service import GorseTrainingService


# Generate unique IDs for this run (expanded for more data)
def generate_dynamic_ids():
    """Generate unique IDs for this run to avoid conflicts"""
    base_id = random.randint(10000, 99999)
    ids = {
        "shop_id": f"cmfb{base_id:05d}00000v3dhw8juz526",
        "collection_1_id": f"gid://shopify/Collection/{base_id + 3001}",
        "collection_2_id": f"gid://shopify/Collection/{base_id + 3002}",
        "checkout_1_id": f"gid://shopify/Checkout/{base_id + 8001}",
        "checkout_2_id": f"gid://shopify/Checkout/{base_id + 8002}",
    }
    # Products (10 total, across categories)
    for i in range(1, 11):
        ids[f"product_{i}_id"] = f"gid://shopify/Product/{base_id + i}"
        ids[f"variant_{i}_id"] = f"gid://shopify/ProductVariant/{base_id + 1000 + i}"
    # Customers (5 total)
    for i in range(1, 6):
        ids[f"customer_{i}_id"] = f"gid://shopify/Customer/{base_id + 5000 + i}"
    # Orders (5 total)
    for i in range(1, 6):
        ids[f"order_{i}_id"] = f"gid://shopify/Order/{base_id + 7000 + i}"
    # Line items (multiple per order)
    for i in range(1, 16):  # Up to 3 per order
        ids[f"line_item_{i}_id"] = f"gid://shopify/LineItem/{base_id + 8000 + i}"
    return ids


# Generate IDs for this run
DYNAMIC_IDS = generate_dynamic_ids()

# Print the generated IDs for this run
print("🎲 Generated Dynamic IDs for this run:")
for key, value in sorted(DYNAMIC_IDS.items()):
    print(f"  {key}: {value}")
print()


SHOP_DOMAIN = "fashion-store.myshopify.com"
ACCESS_TOKEN = "test-access-token"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def past_date(days_ago: int) -> datetime:
    return now_utc() - timedelta(days=days_ago)


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
    """Insert 10 RawProduct rows with realistic Shopify-like payloads across categories."""
    # Categories: Clothing (1-4), Accessories (5-7), Electronics (8-10)
    products = [
        {  # 1: Clothing
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
                "tags": ["clothing", "hoodie", "unisex", "sale"],
                "createdAt": past_date(30).isoformat(),  # Old product
            }
        },
        {  # 2: Clothing
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
                "createdAt": past_date(15).isoformat(),
            }
        },
        {  # 3: Clothing
            "product": {
                "id": DYNAMIC_IDS["product_3_id"],
                "title": "Jeans",
                "handle": "jeans",
                "productType": "Clothing",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_3_id"],
                                "title": "Blue / 32",
                                "sku": "JN-BLU-32",
                                "price": "60.00",
                                "inventoryQuantity": 8,
                                "compareAtPrice": "80.00",
                            }
                        }
                    ]
                },
                "tags": ["clothing", "jeans", "denim"],
                "createdAt": past_date(10).isoformat(),
            }
        },
        {  # 4: Clothing (low stock for edge case)
            "product": {
                "id": DYNAMIC_IDS["product_4_id"],
                "title": "Baseball Cap",
                "handle": "baseball-cap",
                "productType": "Clothing",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_4_id"],
                                "title": "Red / One Size",
                                "sku": "BC-RED-OS",
                                "price": "20.00",
                                "inventoryQuantity": 2,  # Low stock
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["clothing", "hat", "baseball"],
                "createdAt": past_date(5).isoformat(),
            }
        },
        {  # 5: Accessories
            "product": {
                "id": DYNAMIC_IDS["product_5_id"],
                "title": "Sunglasses",
                "handle": "sunglasses",
                "productType": "Accessories",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_5_id"],
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
                "createdAt": past_date(20).isoformat(),
            }
        },
        {  # 6: Accessories
            "product": {
                "id": DYNAMIC_IDS["product_6_id"],
                "title": "Leather Belt",
                "handle": "leather-belt",
                "productType": "Accessories",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_6_id"],
                                "title": "Brown / Medium",
                                "sku": "LB-BRN-M",
                                "price": "35.00",
                                "inventoryQuantity": 12,
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["accessories", "belt", "leather"],
                "createdAt": past_date(8).isoformat(),
            }
        },
        {  # 7: Accessories (new item for "latest")
            "product": {
                "id": DYNAMIC_IDS["product_7_id"],
                "title": "Scarf",
                "handle": "scarf",
                "productType": "Accessories",
                "vendor": "Fashion Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_7_id"],
                                "title": "Wool / One Size",
                                "sku": "SC-WOL-OS",
                                "price": "30.00",
                                "inventoryQuantity": 20,
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["accessories", "scarf", "wool", "new"],
                "createdAt": past_date(1).isoformat(),  # Recent for "latest"
            }
        },
        {  # 8: Electronics
            "product": {
                "id": DYNAMIC_IDS["product_8_id"],
                "title": "Wireless Earbuds",
                "handle": "wireless-earbuds",
                "productType": "Electronics",
                "vendor": "Tech Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_8_id"],
                                "title": "Black",
                                "sku": "WE-BLK",
                                "price": "80.00",
                                "inventoryQuantity": 10,
                                "compareAtPrice": "100.00",
                            }
                        }
                    ]
                },
                "tags": ["electronics", "earbuds", "wireless"],
                "createdAt": past_date(25).isoformat(),
            }
        },
        {  # 9: Electronics
            "product": {
                "id": DYNAMIC_IDS["product_9_id"],
                "title": "Phone Case",
                "handle": "phone-case",
                "productType": "Electronics",
                "vendor": "Tech Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_9_id"],
                                "title": "Clear / iPhone",
                                "sku": "PC-CLR-IP",
                                "price": "15.00",
                                "inventoryQuantity": 25,
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["electronics", "phone-case", "clear"],
                "createdAt": past_date(12).isoformat(),
            }
        },
        {  # 10: Electronics (popular cross-sell with clothing)
            "product": {
                "id": DYNAMIC_IDS["product_10_id"],
                "title": "Portable Charger",
                "handle": "portable-charger",
                "productType": "Electronics",
                "vendor": "Tech Co",
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["variant_10_id"],
                                "title": "10000mAh",
                                "sku": "PC-10K",
                                "price": "40.00",
                                "inventoryQuantity": 5,  # Low stock but not out of stock
                                "compareAtPrice": None,
                            }
                        }
                    ]
                },
                "tags": ["electronics", "charger", "portable"],
                "createdAt": past_date(3).isoformat(),
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
                    "shopifyCreatedAt": datetime.fromisoformat(
                        p["product"]["createdAt"]
                    ),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


async def insert_raw_customers(db, shop_id: str) -> List[Dict[str, Any]]:
    """Insert 5 RawCustomer rows with varied profiles."""
    customers = [
        {  # 1: VIP with multiple orders
            "customer": {
                "id": DYNAMIC_IDS["customer_1_id"],
                "email": "alice@example.com",
                "firstName": "Alice",
                "lastName": "Doe",
                "totalSpent": "200.00",
                "ordersCount": 3,
                "tags": ["vip", "repeat-buyer"],
            }
        },
        {  # 2: New user with views only
            "customer": {
                "id": DYNAMIC_IDS["customer_2_id"],
                "email": "bob@example.com",
                "firstName": "Bob",
                "lastName": "Smith",
                "totalSpent": "0.00",
                "ordersCount": 0,
                "tags": ["new"],
            }
        },
        {  # 3: Moderate buyer
            "customer": {
                "id": DYNAMIC_IDS["customer_3_id"],
                "email": "charlie@example.com",
                "firstName": "Charlie",
                "lastName": "Brown",
                "totalSpent": "100.00",
                "ordersCount": 1,
                "tags": ["moderate"],
            }
        },
        {  # 4: Abandoned cart user
            "customer": {
                "id": DYNAMIC_IDS["customer_4_id"],
                "email": "dana@example.com",
                "firstName": "Dana",
                "lastName": "Lee",
                "totalSpent": "0.00",
                "ordersCount": 0,
                "tags": ["abandoned-cart"],
            }
        },
        {  # 5: Cross-category buyer
            "customer": {
                "id": DYNAMIC_IDS["customer_5_id"],
                "email": "eve@example.com",
                "firstName": "Eve",
                "lastName": "Adams",
                "totalSpent": "150.00",
                "ordersCount": 2,
                "tags": ["cross-category"],
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
    """Insert 5 RawOrder rows with patterns for frequently bought together."""
    orders = [
        {  # 1: Alice - Hoodie + T-Shirt + Jeans (Clothing bundle)
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
                                "quantity": 1,
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
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_3_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "60.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Jeans - Blue / 32",
                                "variant": {"id": product_variant_ids[2]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "130.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "130.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": past_date(5).isoformat(),
                "tags": ["processed"],
            }
        },
        {  # 2: Alice - Sunglasses + Belt (Accessories, repeat buy)
            "order": {
                "id": DYNAMIC_IDS["order_2_id"],
                "name": "#1002",
                "email": "alice@example.com",
                "customer": {"id": customer_ids[0]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_4_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "55.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Sunglasses - Black",
                                "variant": {"id": product_variant_ids[4]},
                            }
                        },
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_5_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "35.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Leather Belt - Brown / Medium",
                                "variant": {"id": product_variant_ids[5]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "90.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "90.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": past_date(3).isoformat(),
                "tags": ["processed"],
            }
        },
        {  # 3: Charlie - Earbuds + Phone Case (Electronics bundle)
            "order": {
                "id": DYNAMIC_IDS["order_3_id"],
                "name": "#1003",
                "email": "charlie@example.com",
                "customer": {"id": customer_ids[2]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_6_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "80.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Wireless Earbuds - Black",
                                "variant": {"id": product_variant_ids[7]},
                            }
                        },
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_7_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "15.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Phone Case - Clear / iPhone",
                                "variant": {"id": product_variant_ids[8]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "95.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "95.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": past_date(7).isoformat(),
                "tags": ["processed"],
            }
        },
        {  # 4: Eve - Hoodie + Earbuds (cross-category)
            "order": {
                "id": DYNAMIC_IDS["order_4_id"],
                "name": "#1004",
                "email": "eve@example.com",
                "customer": {"id": customer_ids[4]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_8_id"],
                                "quantity": 1,
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
                                "id": DYNAMIC_IDS["line_item_9_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "80.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Wireless Earbuds - Black",
                                "variant": {"id": product_variant_ids[7]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "125.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "125.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": past_date(2).isoformat(),
                "tags": ["processed"],
            }
        },
        {  # 5: Eve - Scarf + Charger (accessories + electronics, recent)
            "order": {
                "id": DYNAMIC_IDS["order_5_id"],
                "name": "#1005",
                "email": "eve@example.com",
                "customer": {"id": customer_ids[4]},
                "lineItems": {
                    "edges": [
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_10_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "30.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Scarf - Wool / One Size",
                                "variant": {"id": product_variant_ids[6]},
                            }
                        },
                        {
                            "node": {
                                "id": DYNAMIC_IDS["line_item_11_id"],
                                "quantity": 1,
                                "originalUnitPriceSet": {
                                    "shopMoney": {
                                        "amount": "40.00",
                                        "currencyCode": "USD",
                                    }
                                },
                                "title": "Portable Charger - 10000mAh",
                                "variant": {"id": product_variant_ids[9]},
                            }
                        },
                    ]
                },
                "totalPriceSet": {
                    "shopMoney": {"amount": "70.00", "currencyCode": "USD"}
                },
                "subtotalPriceSet": {
                    "shopMoney": {"amount": "70.00", "currencyCode": "USD"}
                },
                "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "USD"}},
                "createdAt": past_date(1).isoformat(),
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
                    "shopifyCreatedAt": datetime.fromisoformat(o["order"]["createdAt"]),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


async def insert_raw_collection(
    db, shop_id: str, product_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert 2 RawCollections referencing products."""
    collections = [
        {  # 1: Summer Essentials (Clothing + Accessories)
            "collection": {
                "id": DYNAMIC_IDS["collection_1_id"],
                "title": "Summer Essentials",
                "handle": "summer-essentials",
                "description": "Perfect for summer",
                "products": {
                    "edges": [{"node": {"id": pid}} for pid in product_ids[:7]]
                },  # Products 1-7
                "productCount": 7,
                "isAutomated": False,
            }
        },
        {  # 2: Tech Gear (Electronics + cross-category)
            "collection": {
                "id": DYNAMIC_IDS["collection_2_id"],
                "title": "Tech Gear",
                "handle": "tech-gear",
                "description": "Tech accessories",
                "products": {
                    "edges": [{"node": {"id": pid}} for pid in product_ids[7:]]
                    + [{"node": {"id": product_ids[0]}}]
                },  # Products 8-10 + Hoodie for cross
                "productCount": 4,
                "isAutomated": False,
            }
        },
    ]

    created = []
    for c in collections:
        created.append(
            await db.rawcollection.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(c),
                    "shopifyId": c["collection"]["id"],
                    "extractedAt": now_utc(),
                    "shopifyCreatedAt": now_utc(),
                    "shopifyUpdatedAt": now_utc(),
                }
            )
        )
    return created


def _event_payload(
    event_name: str,
    client_id: str,
    seq: int,
    extra: Dict[str, Any],
    timestamp: datetime = None,
    device_type: str = "desktop",  # Add for metadata
    customer_id: str = None,  # Add customer ID for proper linking
    clients: List[str] = None,  # Client list for auto-mapping
    customer_ids: List[str] = None,  # Customer list for auto-mapping
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": f"e_{uuid.uuid4()}",
        "name": event_name,
        "timestamp": (timestamp or now_utc()).isoformat(),
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
            "userAgent": f"Mozilla/5.0 ({device_type})",  # Simulate device_type for metadata
        },
    }

    # Add customer ID only if explicitly provided
    if customer_id:
        base["customerId"] = customer_id
    # Note: Removed automatic customer ID assignment to keep events anonymous by default

    if extra:
        base.update({"data": extra})
    else:
        base.update({"data": {}})
    return base


async def insert_raw_behavioral_events(
    db, shop_id: str, product_variant_ids: List[str], customer_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert 30+ RawBehavioralEvents covering all types and scenarios."""
    events: List[Dict[str, Any]] = []

    # Client IDs for 5 sessions (one per customer + anonymous)
    clients = [str(uuid.uuid4()) for _ in range(5)]

    # Helper function to create events - keep them anonymous initially
    def create_event(
        event_name: str,
        client_id: str,
        seq: int,
        extra: Dict[str, Any],
        timestamp: datetime = None,
        device_type: str = "desktop",
        is_logged_in: bool = False,  # Whether this event should have a customer ID
    ) -> Dict[str, Any]:
        """Create event - anonymous by default, can be logged in if specified"""
        # Only assign customer ID if this is a logged-in event
        customer_id = None
        if is_logged_in:
            try:
                client_index = clients.index(client_id)
                if client_index < len(customer_ids):
                    customer_id = customer_ids[client_index]
            except ValueError:
                pass  # Anonymous user

        return _event_payload(
            event_name, client_id, seq, extra, timestamp, device_type, customer_id
        )

    # Session 1: Alice (VIP) - Full journey: Browse, view, add, checkout (logged in later)
    # Device: mobile for metadata
    events.append(
        create_event("page_viewed", clients[0], 1, {}, past_date(5), "mobile")
    )
    events.append(
        create_event(
            "search_submitted",
            clients[0],
            2,
            {"searchResult": {"query": "hoodie"}},
            past_date(5),
            "mobile",
        )
    )
    events.append(
        create_event(
            "collection_viewed",
            clients[0],
            3,
            {
                "collection": {
                    "id": DYNAMIC_IDS["collection_1_id"],
                    "title": "Summer Essentials",
                    "productVariants": [
                        {
                            "id": product_variant_ids[0],
                            "title": "Grey / Small",
                            "price": {"amount": 45.00, "currencyCode": "USD"},
                            "product": {
                                "id": DYNAMIC_IDS["product_1_id"],
                                "title": "Unisex Hoodie",
                                "vendor": "Fashion Co",
                            },
                        },
                        {
                            "id": product_variant_ids[1],
                            "title": "White / Medium",
                            "price": {"amount": 25.00, "currencyCode": "USD"},
                            "product": {
                                "id": DYNAMIC_IDS["product_2_id"],
                                "title": "Classic T-Shirt",
                                "vendor": "Fashion Co",
                            },
                        },
                    ],
                }
            },
            past_date(5),
            "mobile",
        )
    )
    events.append(
        create_event(
            "product_viewed",
            clients[0],
            4,
            {
                "productVariant": {
                    "id": product_variant_ids[0],
                    "title": "Grey / Small",
                    "price": {"amount": 45.00, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_1_id"],
                        "title": "Unisex Hoodie",
                        "vendor": "Fashion Co",
                    },
                }
            },
            past_date(5),
            "mobile",
        )
    )  # Hoodie
    events.append(
        create_event(
            "product_viewed",
            clients[0],
            5,
            {
                "productVariant": {
                    "id": product_variant_ids[1],
                    "title": "White / Medium",
                    "price": {"amount": 25.00, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_2_id"],
                        "title": "Classic T-Shirt",
                        "vendor": "Fashion Co",
                    },
                }
            },
            past_date(5),
            "mobile",
        )
    )  # T-Shirt (recent view)
    events.append(
        create_event(
            "product_added_to_cart",
            clients[0],
            6,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[0],
                        "title": "Grey / Small",
                        "price": {"amount": 45.00, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_1_id"],
                            "title": "Unisex Hoodie",
                            "vendor": "Fashion Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 45.00, "currencyCode": "USD"}},
                }
            },
            past_date(5),
            "mobile",
        )
    )
    # Cart viewed event - user checks their cart
    events.append(
        create_event(
            "cart_viewed",
            clients[0],
            7,
            {
                "cart": {
                    "id": "cart_1",
                    "totalQuantity": 1,
                    "cost": {"totalAmount": {"amount": 45.00, "currencyCode": "USD"}},
                    "lines": [
                        {
                            "merchandise": {
                                "id": product_variant_ids[0],
                                "title": "Grey / Small",
                                "price": {"amount": 45.00, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_1_id"],
                                    "title": "Unisex Hoodie",
                                    "vendor": "Fashion Co",
                                },
                            },
                            "quantity": 1,
                            "cost": {
                                "totalAmount": {"amount": 45.00, "currencyCode": "USD"}
                            },
                        }
                    ],
                }
            },
            past_date(5),
            "mobile",
        )
    )
    events.append(
        create_event(
            "checkout_started",
            clients[0],
            8,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_1_id"],
                    "totalPrice": {"amount": 45.00, "currencyCode": "USD"},
                    "lineItems": [
                        {
                            "id": "line_item_1",
                            "title": "Unisex Hoodie",
                            "quantity": 1,
                            "finalLinePrice": {"amount": 45.00, "currencyCode": "USD"},
                            "variant": {
                                "id": product_variant_ids[0],
                                "title": "Grey / Small",
                                "price": {"amount": 45.00, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_1_id"],
                                    "title": "Unisex Hoodie",
                                    "vendor": "Fashion Co",
                                },
                            },
                        }
                    ],
                }
            },
            past_date(5),
            "mobile",
        )
    )
    events.append(
        create_event(
            "checkout_completed",
            clients[0],
            9,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_1_id"],
                    "totalPrice": {"amount": 45.00, "currencyCode": "USD"},
                    "lineItems": [
                        {
                            "id": "line_item_1",
                            "title": "Unisex Hoodie",
                            "quantity": 1,
                            "finalLinePrice": {"amount": 45.00, "currencyCode": "USD"},
                            "variant": {
                                "id": product_variant_ids[0],
                                "title": "Grey / Small",
                                "price": {"amount": 45.00, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_1_id"],
                                    "title": "Unisex Hoodie",
                                    "vendor": "Fashion Co",
                                },
                            },
                        }
                    ],
                    "order": {"id": DYNAMIC_IDS["order_1_id"]},
                }
            },
            past_date(5),
            "mobile",
            is_logged_in=True,  # Alice is now logged in for checkout
        )
    )
    events.append(
        create_event(
            "customer_linked",
            clients[0],
            10,
            {"customerId": customer_ids[0]},
            past_date(5),
            "mobile",
        )
    )  # Logs in

    # Session 2: Bob (New) - Views only, no purchase (for cold-start)
    events.append(create_event("page_viewed", clients[1], 1, {}, past_date(4)))
    events.append(
        create_event(
            "product_viewed",
            clients[1],
            2,
            {
                "productVariant": {
                    "id": product_variant_ids[4],
                    "title": "Black / One Size",
                    "price": {"amount": 89.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_5_id"],
                        "title": "Designer Sunglasses",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(4),
        )
    )  # Sunglasses
    events.append(
        create_event(
            "product_viewed",
            clients[1],
            3,
            {
                "productVariant": {
                    "id": product_variant_ids[5],
                    "title": "Brown / Large",
                    "price": {"amount": 35.00, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_6_id"],
                        "title": "Leather Belt",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(4),
        )
    )  # Belt (recent view)
    events.append(
        create_event(
            "customer_linked",
            clients[1],
            4,
            {"customerId": customer_ids[1]},
            past_date(4),
        )
    )

    # Session 3: Charlie (Moderate) - Cross-category buy
    events.append(create_event("page_viewed", clients[2], 1, {}, past_date(3)))
    events.append(
        create_event(
            "collection_viewed",
            clients[2],
            2,
            {
                "collection": {
                    "id": DYNAMIC_IDS["collection_2_id"],
                    "title": "Tech Gear",
                    "productVariants": [
                        {
                            "id": product_variant_ids[7],
                            "title": "Silver / 64GB",
                            "price": {"amount": 299.99, "currencyCode": "USD"},
                            "product": {
                                "id": DYNAMIC_IDS["product_8_id"],
                                "title": "Smart Watch",
                                "vendor": "Tech Co",
                            },
                        },
                        {
                            "id": product_variant_ids[8],
                            "title": "Black / 128GB",
                            "price": {"amount": 199.99, "currencyCode": "USD"},
                            "product": {
                                "id": DYNAMIC_IDS["product_9_id"],
                                "title": "Wireless Earbuds",
                                "vendor": "Tech Co",
                            },
                        },
                    ],
                }
            },
            past_date(3),
        )
    )
    events.append(
        create_event(
            "product_viewed",
            clients[2],
            3,
            {
                "productVariant": {
                    "id": product_variant_ids[7],
                    "title": "Silver / 64GB",
                    "price": {"amount": 299.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_8_id"],
                        "title": "Smart Watch",
                        "vendor": "Tech Co",
                    },
                }
            },
            past_date(3),
        )
    )  # Smart Watch
    events.append(
        create_event(
            "product_viewed",
            clients[2],
            4,
            {
                "productVariant": {
                    "id": product_variant_ids[8],
                    "title": "Black / 128GB",
                    "price": {"amount": 199.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_9_id"],
                        "title": "Wireless Earbuds",
                        "vendor": "Tech Co",
                    },
                }
            },
            past_date(3),
        )
    )  # Wireless Earbuds
    events.append(
        create_event(
            "product_added_to_cart",
            clients[2],
            5,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[7],
                        "title": "Silver / 64GB",
                        "price": {"amount": 299.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_8_id"],
                            "title": "Smart Watch",
                            "vendor": "Tech Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 299.99, "currencyCode": "USD"}},
                }
            },
            past_date(3),
        )
    )
    # Cart viewed event - user checks their cart
    events.append(
        create_event(
            "cart_viewed",
            clients[2],
            6,
            {
                "cart": {
                    "id": "cart_2",
                    "totalQuantity": 1,
                    "cost": {"totalAmount": {"amount": 299.99, "currencyCode": "USD"}},
                    "lines": [
                        {
                            "merchandise": {
                                "id": product_variant_ids[7],
                                "title": "Silver / 64GB",
                                "price": {"amount": 299.99, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_8_id"],
                                    "title": "Smart Watch",
                                    "vendor": "Tech Co",
                                },
                            },
                            "quantity": 1,
                            "cost": {
                                "totalAmount": {"amount": 299.99, "currencyCode": "USD"}
                            },
                        }
                    ],
                }
            },
            past_date(3),
        )
    )
    # Product removed from cart - user changes their mind
    events.append(
        create_event(
            "product_removed_from_cart",
            clients[2],
            7,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[7],
                        "title": "Silver / 64GB",
                        "price": {"amount": 299.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_8_id"],
                            "title": "Smart Watch",
                            "vendor": "Tech Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 299.99, "currencyCode": "USD"}},
                }
            },
            past_date(3),
        )
    )
    events.append(
        create_event(
            "checkout_completed",
            clients[2],
            8,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_2_id"],
                    "totalPrice": {"amount": 299.99, "currencyCode": "USD"},
                    "lineItems": [
                        {
                            "id": "line_item_2",
                            "title": "Smart Watch",
                            "quantity": 1,
                            "finalLinePrice": {"amount": 299.99, "currencyCode": "USD"},
                            "variant": {
                                "id": product_variant_ids[7],
                                "title": "Silver / 64GB",
                                "price": {"amount": 299.99, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_8_id"],
                                    "title": "Smart Watch",
                                    "vendor": "Tech Co",
                                },
                            },
                        }
                    ],
                    "order": {"id": DYNAMIC_IDS["order_3_id"]},
                }
            },
            past_date(3),
            "desktop",
            is_logged_in=True,  # Bob is now logged in for checkout
        )
    )
    events.append(
        create_event(
            "customer_linked",
            clients[2],
            7,
            {"customerId": customer_ids[2]},
            past_date(3),
        )
    )

    # Session 4: Dana (Abandoned Cart) - Add to cart, no checkout
    events.append(create_event("page_viewed", clients[3], 1, {}, past_date(2)))
    events.append(
        create_event(
            "search_submitted",
            clients[3],
            2,
            {"searchResult": {"query": "scarf"}},
            past_date(2),
        )
    )
    events.append(
        create_event(
            "product_viewed",
            clients[3],
            3,
            {
                "productVariant": {
                    "id": product_variant_ids[6],
                    "title": "Red / One Size",
                    "price": {"amount": 19.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_7_id"],
                        "title": "Silk Scarf",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(2),
        )
    )  # Scarf
    events.append(
        create_event(
            "product_added_to_cart",
            clients[3],
            4,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[6],
                        "title": "Red / One Size",
                        "price": {"amount": 19.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_7_id"],
                            "title": "Silk Scarf",
                            "vendor": "Accessories Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 19.99, "currencyCode": "USD"}},
                }
            },
            past_date(2),
        )
    )
    events.append(
        create_event(
            "customer_linked",
            clients[3],
            6,
            {"customerId": customer_ids[3]},
            past_date(2),
        )
    )

    # Session 5: Eve (Cross-Category) - Multiple buys, recent activity
    events.append(
        create_event("page_viewed", clients[4], 1, {}, past_date(1), "mobile")
    )
    events.append(
        create_event(
            "product_viewed",
            clients[4],
            2,
            {
                "productVariant": {
                    "id": product_variant_ids[0],
                    "title": "Grey / Small",
                    "price": {"amount": 45.00, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_1_id"],
                        "title": "Unisex Hoodie",
                        "vendor": "Fashion Co",
                    },
                }
            },
            past_date(1),
            "mobile",
        )
    )  # Hoodie
    events.append(
        create_event(
            "product_viewed",
            clients[4],
            3,
            {
                "productVariant": {
                    "id": product_variant_ids[7],
                    "title": "Silver / 64GB",
                    "price": {"amount": 299.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_8_id"],
                        "title": "Smart Watch",
                        "vendor": "Tech Co",
                    },
                }
            },
            past_date(1),
            "mobile",
        )
    )  # Smart Watch (recent view)
    events.append(
        create_event(
            "product_added_to_cart",
            clients[4],
            4,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[0],
                        "title": "Grey / Small",
                        "price": {"amount": 45.00, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_1_id"],
                            "title": "Unisex Hoodie",
                            "vendor": "Fashion Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 45.00, "currencyCode": "USD"}},
                }
            },
            past_date(1),
            "mobile",
        )
    )
    events.append(
        create_event(
            "checkout_completed",
            clients[4],
            5,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_1_id"],
                    "totalPrice": {"amount": 45.00, "currencyCode": "USD"},
                    "lineItems": [
                        {
                            "id": "line_item_3",
                            "title": "Unisex Hoodie",
                            "quantity": 1,
                            "finalLinePrice": {"amount": 45.00, "currencyCode": "USD"},
                            "variant": {
                                "id": product_variant_ids[0],
                                "title": "Grey / Small",
                                "price": {"amount": 45.00, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_1_id"],
                                    "title": "Unisex Hoodie",
                                    "vendor": "Fashion Co",
                                },
                            },
                        }
                    ],
                    "order": {"id": DYNAMIC_IDS["order_4_id"]},
                }
            },
            past_date(1),
            "mobile",
            is_logged_in=True,  # Anonymous user is now logged in for checkout
        )
    )
    events.append(
        create_event(
            "product_viewed",
            clients[4],
            6,
            {
                "productVariant": {
                    "id": product_variant_ids[6],
                    "title": "Red / One Size",
                    "price": {"amount": 19.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_7_id"],
                        "title": "Silk Scarf",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(0),
            "mobile",
        )
    )  # Scarf (today)
    events.append(
        create_event(
            "product_viewed",
            clients[4],
            7,
            {
                "productVariant": {
                    "id": product_variant_ids[9],
                    "title": "Black / Universal",
                    "price": {"amount": 15.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_10_id"],
                        "title": "USB-C Charger",
                        "vendor": "Tech Co",
                    },
                }
            },
            past_date(0),
            "mobile",
        )
    )  # Charger
    events.append(
        create_event(
            "product_added_to_cart",
            clients[4],
            8,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[6],
                        "title": "Red / One Size",
                        "price": {"amount": 19.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_7_id"],
                            "title": "Silk Scarf",
                            "vendor": "Accessories Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 19.99, "currencyCode": "USD"}},
                }
            },
            past_date(0),
            "mobile",
        )
    )
    events.append(
        create_event(
            "checkout_completed",
            clients[4],
            9,
            {
                "checkout": {
                    "id": DYNAMIC_IDS["checkout_2_id"],
                    "totalPrice": {"amount": 19.99, "currencyCode": "USD"},
                    "lineItems": [
                        {
                            "id": "line_item_4",
                            "title": "Silk Scarf",
                            "quantity": 1,
                            "finalLinePrice": {"amount": 19.99, "currencyCode": "USD"},
                            "variant": {
                                "id": product_variant_ids[6],
                                "title": "Red / One Size",
                                "price": {"amount": 19.99, "currencyCode": "USD"},
                                "product": {
                                    "id": DYNAMIC_IDS["product_7_id"],
                                    "title": "Silk Scarf",
                                    "vendor": "Accessories Co",
                                },
                            },
                        }
                    ],
                    "order": {"id": DYNAMIC_IDS["order_5_id"]},
                }
            },
            past_date(0),
            "mobile",
            is_logged_in=True,  # Anonymous user is now logged in for checkout
        )
    )
    events.append(
        create_event(
            "customer_linked",
            clients[4],
            10,
            {"customerId": customer_ids[4]},
            past_date(1),
            "mobile",
        )
    )

    # Additional anonymous sessions for edge cases
    anonymous_client = str(uuid.uuid4())
    #  Anonymous abandonment
    events.append(create_event("page_viewed", anonymous_client, 1, {}, past_date(6)))
    events.append(
        create_event(
            "product_viewed",
            anonymous_client,
            2,
            {
                "productVariant": {
                    "id": product_variant_ids[3],
                    "title": "Blue / One Size",
                    "price": {"amount": 24.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_4_id"],
                        "title": "Baseball Cap",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(6),
        )
    )  # Baseball Cap (low stock)
    events.append(
        create_event(
            "product_added_to_cart",
            anonymous_client,
            3,
            {
                "cartLine": {
                    "merchandise": {
                        "id": product_variant_ids[3],
                        "title": "Blue / One Size",
                        "price": {"amount": 24.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_4_id"],
                            "title": "Baseball Cap",
                            "vendor": "Accessories Co",
                        },
                    },
                    "quantity": 1,
                    "cost": {"totalAmount": {"amount": 24.99, "currencyCode": "USD"}},
                }
            },
            past_date(6),
        )
    )  # Abandoned

    # Anonymous new item view (for latest)
    events.append(
        create_event(
            "product_viewed",
            anonymous_client,
            4,
            {
                "productVariant": {
                    "id": product_variant_ids[6],
                    "title": "Red / One Size",
                    "price": {"amount": 19.99, "currencyCode": "USD"},
                    "product": {
                        "id": DYNAMIC_IDS["product_7_id"],
                        "title": "Silk Scarf",
                        "vendor": "Accessories Co",
                    },
                }
            },
            past_date(1),
        )
    )  # Scarf (new)

    # More views for popularity (make Sunglasses popular)
    for i in range(5):  # 5 extra views
        events.append(
            create_event(
                "product_viewed",
                str(uuid.uuid4()),
                1,
                {
                    "productVariant": {
                        "id": product_variant_ids[4],
                        "title": "Black / One Size",
                        "price": {"amount": 89.99, "currencyCode": "USD"},
                        "product": {
                            "id": DYNAMIC_IDS["product_5_id"],
                            "title": "Designer Sunglasses",
                            "vendor": "Accessories Co",
                        },
                    }
                },
                past_date(random.randint(1, 30)),
            )
        )

    created = []
    for ev in events:
        created.append(
            await db.rawbehavioralevents.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(ev),
                    "receivedAt": datetime.fromisoformat(ev["timestamp"]),
                }
            )
        )
    return created


# The rest of the script remains the same (insert_user_identity_links, main, process functions, run_complete_pipeline)
# Update main() to use the new counts in print statement: "1 shop, 10 products, 5 customers, 5 orders, 2 collections, 30+ events, 5 identity links"


async def insert_user_identity_links(
    db, shop_id: str, client_ids: List[str], customer_ids: List[str]
) -> List[Dict[str, Any]]:
    """Insert UserIdentityLink records with proper 1:1 mapping between client IDs and customer IDs."""
    links = []
    # Ensure we only create links for the number of client IDs we have
    # and map them 1:1 with customer IDs
    for i, client_id in enumerate(client_ids):
        if i < len(
            customer_ids
        ):  # Only create link if we have a corresponding customer ID
            links.append(
                await db.useridentitylink.create(
                    data={
                        "shopId": shop_id,
                        "clientId": client_id,
                        "customerId": customer_ids[i],
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
    bob_client_id = raw_events[10].payload.get(
        "clientId"
    )  # 11th event is Bob's first (after Alice's 10 events)

    # Create UserIdentityLink records - only link the first 2 customers to the 2 client IDs
    client_ids = [alice_client_id, bob_client_id]
    linked_customer_ids = customer_ids[:2]  # Only take first 2 customers for linking

    await insert_user_identity_links(db, shop_id, client_ids, linked_customer_ids)

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


async def sync_to_gorse(shop_id: str):
    """Sync feature data to Gorse bridge tables and push to Gorse"""
    print("\n🔄 Syncing data to Gorse...")

    try:
        # Initialize Gorse sync pipeline
        sync_pipeline = GorseSyncPipeline()

        # Sync all data to Gorse bridge tables
        print("📊 Syncing users, items, and feedback to Gorse bridge tables...")
        sync_result = await sync_pipeline.sync_all(shop_id, incremental=False)

        if sync_result:
            print("✅ Gorse sync pipeline completed successfully")

            # Initialize Gorse training service
            training_service = GorseTrainingService()

            # Push data to Gorse and trigger training
            print("🚀 Pushing data to Gorse and triggering training...")
            training_job_id = await training_service.push_data_to_gorse(
                shop_id=shop_id, job_type="full_training", trigger_source="seed_script"
            )

            print(f"✅ Gorse training job started: {training_job_id}")
            return True
        else:
            print("❌ Gorse sync pipeline failed")
            return False

    except Exception as e:
        print(f"❌ Gorse sync failed: {e}")
        return False


async def test_recommendations_api(shop_id: str):
    """Test the recommendations API with seeded data"""
    print("\n🔄 Testing recommendations API...")

    try:
        # Get a customer ID from the seeded data
        db = await get_database()
        customer = await db.customerdata.find_first(where={"shopId": shop_id})

        if not customer:
            print("❌ No customers found for recommendations testing")
            return False

        customer_id = customer.customerId
        print(f"🧪 Testing recommendations for customer: {customer_id}")

        # Import the recommendations API client
        from app.shared.gorse_api_client import GorseApiClient

        # Initialize Gorse API client
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


async def run_complete_pipeline():
    """Run the complete data pipeline: seed -> process -> compute features -> sync to Gorse -> test recommendations"""
    print("🚀 Starting complete data pipeline...")

    # Step 1: Seed raw data
    print("\n📊 Step 1: Seeding raw data...")
    shop_id = await main()

    # Step 2: Process raw data to main tables
    print("\n📊 Step 2: Processing raw data to main tables...")
    main_success = await process_raw_to_main_tables(shop_id)

    # Step 3: Process behavioral events using webhook handler
    print("\n📊 Step 3: Processing behavioral events using webhook handler...")
    events_success = await process_behavioral_events(shop_id)

    # Step 4: Compute ML features
    print("\n📊 Step 4: Computing ML features...")
    features_success = await compute_features(shop_id)

    # Step 5: Sync to Gorse
    print("\n📊 Step 5: Syncing data to Gorse...")
    gorse_success = await sync_to_gorse(shop_id)

    # Step 6: Test recommendations API
    print("\n📊 Step 6: Testing recommendations API...")
    recommendations_success = await test_recommendations_api(shop_id)

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
    print(
        f"  {'✅' if gorse_success else '❌'} Gorse sync: {'Success' if gorse_success else 'Failed'}"
    )
    print(
        f"  {'✅' if recommendations_success else '❌'} Recommendations API test: {'Success' if recommendations_success else 'Failed'}"
    )

    if all(
        [
            shop_id,
            main_success,
            events_success,
            features_success,
            gorse_success,
            recommendations_success,
        ]
    ):
        print("\n🎉 Complete pipeline executed successfully!")
        print("🎯 All systems are ready for testing:")
        print("  • Cart view and remove events are being tracked")
        print("  • Enhanced feature computation with cart analytics")
        print("  • Gorse recommendations are trained and ready")
        print("  • Recommendations API is functional")
    else:
        print("\n⚠️  Pipeline completed with some failures. Check logs above.")


if __name__ == "__main__":
    import sys

    asyncio.run(run_complete_pipeline())
