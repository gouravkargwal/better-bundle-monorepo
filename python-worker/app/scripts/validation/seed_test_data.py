"""
Seed test data into PostgreSQL in Shopify-like format for recommendation validation.

Creates:
  - A fake Shop record to trigger the feature computation pipeline
  - 30 products across 5 categories (Electronics, Clothing, Home & Garden, Sports, Accessories)
  - 5 customers with clear preference patterns
  - Orders that match each customer's preference profile
  - Collection associations

Data is inserted in the same format Shopify would send it, so the existing
feature computation pipeline processes it naturally.

Run:
  uv run python-worker/app/scripts/validation/seed_test_data.py
"""

import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import sqlalchemy as sa

from app.core.database.session import get_session_context
from app.core.database.models.product_data import ProductData
from app.core.database.models.customer_data import CustomerData
from app.core.database.models.order_data import OrderData, LineItemData
from app.core.database.models.collection_data import CollectionData
from app.core.database.models.shop import Shop

SHOP_ID = "validation_test_shop"
SHOP_DOMAIN = "validation-test-shop.myshopify.com"

# ── Products in Shopify format ──────────────────────────────────────────────
# (title, product_type, vendor, price, tags, description)
PRODUCTS = [
    # Electronics
    ("Premium Wireless Earbuds", "Electronics", "SoundMax", 79.99,
     ["electronics", "audio", "wireless", "bluetooth"],
     "High-quality wireless earbuds with active noise cancellation and 24hr battery life."),
    ("USB-C Fast Charger 65W", "Electronics", "ChargePro", 24.99,
     ["electronics", "charger", "usb-c", "fast-charging"],
     "65W GaN fast charger compatible with all USB-C devices including laptops and tablets."),
    ("Silicone Phone Case", "Electronics", "ArmorCase", 19.99,
     ["electronics", "phone-case", "silicone", "protection"],
     "Shockproof silicone phone case with raised edges for screen protection."),
    ("Portable Bluetooth Speaker", "Electronics", "SoundMax", 49.99,
     ["electronics", "audio", "speaker", "bluetooth", "waterproof"],
     "Portable waterproof bluetooth speaker with 360° sound and 12hr battery."),
    ("Adjustable Laptop Stand", "Electronics", "ErgoHome", 34.99,
     ["electronics", "accessories", "laptop", "ergonomic"],
     "Adjustable aluminum laptop stand with ventilation design."),
    ("20000mAh Power Bank", "Electronics", "ChargePro", 39.99,
     ["electronics", "charger", "power-bank", "portable"],
     "20000mAh high-capacity portable power bank with dual USB output."),
    # Clothing
    ("Premium Cotton Hoodie", "Clothing", "ComfortWear", 59.99,
     ["clothing", "hoodie", "cotton", "casual"],
     "Comfortable cotton blend hoodie with fleece lining."),
    ("Slim Fit Stretch Jeans", "Clothing", "DenimCo", 44.99,
     ["clothing", "jeans", "denim", "slim-fit"],
     "Stretch denim slim fit jeans with modern tapered leg."),
    ("Lightweight Running Shoes", "Clothing", "SportFlex", 89.99,
     ["clothing", "shoes", "running", "athletic"],
     "Lightweight running shoes with responsive cushioning and breathable mesh."),
    ("Wool Blend Crew Sweater", "Clothing", "ComfortWear", 69.99,
     ["clothing", "sweater", "wool", "winter"],
     "Warm wool blend crew neck sweater perfect for layering."),
    ("Classic Denim Jacket", "Clothing", "DenimCo", 79.99,
     ["clothing", "jacket", "denim", "classic"],
     "Classic denim jacket with button closure and chest pockets."),
    ("Essential Cotton T-Shirt", "Clothing", "ComfortWear", 24.99,
     ["clothing", "t-shirt", "cotton", "essential"],
     "Soft 100% organic cotton t-shirt available in multiple colors."),
    # Home & Garden
    ("Hand-crafted Ceramic Plant Pot", "Home & Garden", "GreenHome", 29.99,
     ["home-garden", "planter", "ceramic", "decor"],
     "Hand-crafted ceramic plant pot with drainage hole and bamboo tray."),
    ("Organic Bamboo Cutting Board", "Home & Garden", "GreenHome", 24.99,
     ["home-garden", "kitchen", "bamboo", "cutting-board"],
     "Organic bamboo cutting board set with juice groove."),
    ("Outdoor LED String Lights", "Home & Garden", "LightUp", 15.99,
     ["home-garden", "lighting", "led", "outdoor"],
     "10m waterproof outdoor LED string lights with 20 warm bulbs."),
    ("Ultrasonic Aromatherapy Diffuser", "Home & Garden", "GreenHome", 34.99,
     ["home-garden", "aromatherapy", "diffuser", "wellness"],
     "Ultrasonic essential oil diffuser with LED mood lighting and auto shut-off."),
    ("5-Piece Garden Tool Set", "Home & Garden", "GreenHome", 39.99,
     ["home-garden", "gardening", "tools", "set"],
     "5-piece stainless steel garden tool set with ergonomic handles."),
    ("Decorative Throw Pillow Set", "Home & Garden", "LightUp", 29.99,
     ["home-garden", "decor", "pillow", "throw"],
     "Set of 2 decorative throw pillows with removable covers."),
    # Sports & Fitness
    ("Non-Slip Yoga Mat", "Sports & Fitness", "FitLife", 29.99,
     ["sports", "yoga", "fitness", "exercise"],
     "Non-slip extra thick yoga mat with carrying strap, 6mm thickness."),
    ("Moisture-Wicking Running Headband", "Sports & Fitness", "FitLife", 9.99,
     ["sports", "running", "headband", "accessories"],
     "Moisture-wicking running headband that stays in place during workouts."),
    ("High-Density Foam Roller", "Sports & Fitness", "FitLife", 19.99,
     ["sports", "recovery", "foam-roller", "fitness"],
     "High-density foam roller for muscle recovery and myofascial release."),
    ("Insulated Water Bottle 500ml", "Sports & Fitness", "FitLife", 14.99,
     ["sports", "water-bottle", "insulated", "hydration"],
     "Double-wall insulated stainless steel water bottle, keeps drinks cold 24hrs."),
    ("Resistance Bands Set", "Sports & Fitness", "FitLife", 12.99,
     ["sports", "resistance-bands", "workout", "home-gym"],
     "Set of 5 resistance bands with different tension levels for home workouts."),
    ("Speed Jump Rope", "Sports & Fitness", "FitLife", 8.99,
     ["sports", "jump-rope", "cardio", "fitness"],
     "Adjustable speed jump rope with ball bearings for smooth rotation."),
    # Accessories
    ("Printed Silk Scarf", "Accessories", "LuxeStyle", 34.99,
     ["accessories", "scarf", "silk", "fashion"],
     "Luxury silk scarf with hand-printed pattern, 90x90cm."),
    ("Adjustable Baseball Cap", "Accessories", "LuxeStyle", 19.99,
     ["accessories", "cap", "hat", "casual"],
     "Adjustable cotton baseball cap with embroidered ventilation eyelets."),
    ("Genuine Leather Belt", "Accessories", "LuxeStyle", 39.99,
     ["accessories", "belt", "leather", "formal"],
     "Genuine leather belt with brushed metal buckle, 35mm width."),
    ("UV400 Designer Sunglasses", "Accessories", "LuxeStyle", 149.99,
     ["accessories", "sunglasses", "designer", "uv-protection"],
     "UV400 protection designer sunglasses with polarized lenses."),
    ("Organic Canvas Tote Bag", "Accessories", "EcoCarry", 24.99,
     ["accessories", "bag", "tote", "canvas", "eco-friendly"],
     "Organic cotton canvas tote bag with reinforced stitching."),
    ("Knitted Wool Beanie", "Accessories", "ComfortWear", 14.99,
     ["accessories", "beanie", "wool", "winter", "hat"],
     "Soft knitted wool beanie with fleece lining for extra warmth."),
]

# ── Customer preference patterns ───────────────────────────────────────────
# (customer_id, first_name, last_name, email, main_category, secondary_category, order_count, mix_ratio)
CUSTOMER_PATTERNS = [
    ("alice_power", "Alice", "Johnson", "alice@test.com", "Electronics", "Accessories", 8, 0.85),
    ("bob_budget", "Bob", "Smith", "bob@test.com", "Home & Garden", "Sports & Fitness", 5, 0.90),
    ("carol_fashion", "Carol", "Williams", "carol@test.com", "Clothing", "Accessories", 6, 0.80),
    ("dave_fitness", "Dave", "Brown", "dave@test.com", "Sports & Fitness", "Electronics", 7, 0.85),
    ("eve_mixed", "Eve", "Davis", "eve@test.com", None, None, 10, 0.0),  # buys from all
]


async def seed():
    print("=" * 60)
    print("Seeding test data for recommendation validation")
    print("=" * 60)

    async with get_session_context() as session:
        # ── 1. VERIFY SHOP ────────────────────────────────────────────────
        print("\n🏪 Verifying shop exists...")
        existing_shop = await session.get(Shop, SHOP_ID)
        if not existing_shop:
            print("   ❌ Shop not found! Run seed_shop.py first:")
            print("      uv run python-worker/app/scripts/validation/seed_shop.py")
            return
        print("   ✅ Shop found")

        # ── 2. PRODUCTS ────────────────────────────────────────────────────
        print(f"\n📦 Creating {len(PRODUCTS)} products...")
        cat_map = {}  # category -> [(product_id, title, price)]

        for title, ptype, vendor, price, tags, description in PRODUCTS:
            product_id = f"prod_{title.lower().replace(' ', '_')[:40]}"
            handle = product_id.replace("prod_", "").replace("_", "-")
            cat_key = ptype.lower().replace(" & ", "_").replace(" ", "_")
            cat_map.setdefault(cat_key, []).append((product_id, title, price))

            existing = (await session.execute(
                sa.select(ProductData).where(
                    ProductData.shop_id == SHOP_ID,
                    ProductData.product_id == product_id,
                )
            )).scalar_one_or_none()
            if existing:
                continue

            product = ProductData(
                shop_id=SHOP_ID,
                product_id=product_id,
                title=title,
                handle=handle,
                description=description,
                product_type=ptype,
                vendor=vendor,
                tags=tags,
                price=price,
                compare_at_price=round(price * 1.3, 2),
                status="active",
                is_active=True,
            )
            session.add(product)

        await session.commit()
        print(f"   ✅ {len(PRODUCTS)} products ready")

        # ── 3. CUSTOMERS ───────────────────────────────────────────────────
        print(f"\n👤 Creating {len(CUSTOMER_PATTERNS)} customers...")
        for cid, first, last, email, _, _, _, _ in CUSTOMER_PATTERNS:
            existing = (await session.execute(
                sa.select(CustomerData).where(
                    CustomerData.shop_id == SHOP_ID,
                    CustomerData.customer_id == cid,
                )
            )).scalar_one_or_none()
            if existing:
                continue

            registered = datetime.now(timezone.utc) - timedelta(days=random.randint(30, 90))

            customer = CustomerData(
                shop_id=SHOP_ID,
                customer_id=cid,
                first_name=first,
                last_name=last,
                state="enabled",
                order_count=0,
                total_spent=0.0,
                created_at=registered,
                updated_at=registered,
                verified_email=True,
                tax_exempt=False,
            )
            session.add(customer)

        await session.commit()
        print(f"   ✅ {len(CUSTOMER_PATTERNS)} customers ready")

        # ── 4. ORDERS ──────────────────────────────────────────────────────
        print("\n📋 Creating orders with known preference patterns...")
        order_count = 0
        base_time = datetime.now(timezone.utc) - timedelta(days=30)

        for cid, first, last, email, main_cat, sec_cat, num_orders, mix_ratio in CUSTOMER_PATTERNS:
            customer = (await session.execute(
                sa.select(CustomerData).where(
                    CustomerData.shop_id == SHOP_ID,
                    CustomerData.customer_id == cid,
                )
            )).scalar_one_or_none()
            if not customer:
                continue

            total_spent = 0.0
            order_ids = []

            for i in range(num_orders):
                order_id = f"gid://shopify/Order/{cid}_{i}"

                existing_order = (await session.execute(
                    sa.select(OrderData).where(
                        OrderData.shop_id == SHOP_ID,
                        OrderData.order_id == order_id,
                    )
                )).scalar_one_or_none()
                if existing_order:
                    total_spent += existing_order.total_amount
                    order_ids.append(order_id)
                    continue

                # Pick products according to preference pattern
                if main_cat is None:
                    all_items = [item for items in cat_map.values() for item in items]
                    chosen = random.sample(all_items, min(2, len(all_items)))
                elif random.random() < mix_ratio:
                    chosen_items = cat_map.get(main_cat.lower().replace(" & ", "_").replace(" ", "_"), [])
                    chosen = random.sample(chosen_items, min(2, len(chosen_items)))
                else:
                    sec_items = cat_map.get(sec_cat.lower().replace(" & ", "_").replace(" ", "_"), [])
                    chosen = random.sample(sec_items, min(2, len(sec_items)))

                subtotal = sum(p[2] for p in chosen)
                total_tax = round(subtotal * 0.08, 2)
                total_price = subtotal + total_tax
                order_date = base_time + timedelta(hours=i * 24)

                order = OrderData(
                    shop_id=SHOP_ID,
                    order_id=order_id,
                    customer_id=cid,
                    customer_display_name=f"{first} {last}",
                    currency_code="USD",
                    total_amount=total_price,
                    subtotal_amount=subtotal,
                    total_tax_amount=total_tax,
                    total_outstanding_amount=0.0,
                    order_date=order_date,
                    created_at=order_date,
                    updated_at=order_date,
                    processed_at=order_date,
                    cancelled_at=None,
                    financial_status="paid",
                    fulfillment_status="fulfilled",
                    order_status="closed",
                    note=f"Validation order for {first} {last}",
                )

                for pid, ptitle, pprice in chosen:
                    order.line_items.append(LineItemData(
                        product_id=pid,
                        title=ptitle,
                        quantity=random.randint(1, 3),
                        price=pprice,
                    ))

                session.add(order)
                order_count += 1
                total_spent += total_price
                order_ids.append(order_id)

            # Update customer order stats
            customer.order_count = num_orders
            customer.total_spent = total_spent
            customer.last_order_date = base_time + timedelta(hours=(num_orders - 1) * 24)

        await session.commit()
        print(f"   ✅ {order_count} orders created with preference patterns")

        # ── 4b. REFUNDED ORDER (for negative feedback testing) ──────────
        refund_order_id = "gid://shopify/Order/refunded_test"
        existing_refund = (await session.execute(
            sa.select(OrderData).where(
                OrderData.shop_id == SHOP_ID,
                OrderData.order_id == refund_order_id,
            )
        )).scalar_one_or_none()
        if not existing_refund:
            refund_date = base_time + timedelta(days=2)
            order = OrderData(
                shop_id=SHOP_ID,
                order_id=refund_order_id,
                customer_id="alice_power",
                customer_display_name="Alice Johnson",
                currency_code="USD",
                total_amount=79.99,
                subtotal_amount=79.99,
                total_tax_amount=0.0,
                total_refunded_amount=79.99,
                total_outstanding_amount=0.0,
                order_date=refund_date,
                created_at=refund_date,
                updated_at=refund_date + timedelta(days=5),
                processed_at=refund_date,
                cancelled_at=refund_date + timedelta(days=5),
                financial_status="refunded",
                fulfillment_status="returned",
                order_status="closed",
                note="Refunded order for negative feedback testing",
            )
            order.line_items.append(LineItemData(
                product_id="prod_premium_wireless_earbuds",
                title="Premium Wireless Earbuds",
                quantity=1,
                price=79.99,
            ))
            session.add(order)
            await session.commit()
            print(f"   ✅ 1 refunded order created")
        else:
            print(f"   ✅ Refunded order already exists")

        # ── 5. COLLECTIONS (one per category) ────────────────────────────
        print(f"\n📁 Creating collections...")
        collections_data = [
            ("cat_electronics", "Electronics", "electronics", ["Premium Wireless Earbuds", "USB-C Fast Charger 65W", "Silicone Phone Case", "Portable Bluetooth Speaker", "Adjustable Laptop Stand", "20000mAh Power Bank"]),
            ("cat_clothing", "Clothing", "clothing", ["Premium Cotton Hoodie", "Slim Fit Stretch Jeans", "Lightweight Running Shoes", "Wool Blend Crew Sweater", "Classic Denim Jacket", "Essential Cotton T-Shirt"]),
            ("cat_home_garden", "Home & Garden", "home-garden", ["Hand-crafted Ceramic Plant Pot", "Organic Bamboo Cutting Board", "Outdoor LED String Lights", "Ultrasonic Aromatherapy Diffuser", "5-Piece Garden Tool Set", "Decorative Throw Pillow Set"]),
            ("cat_sports", "Sports & Fitness", "sports-fitness", ["Non-Slip Yoga Mat", "Moisture-Wicking Running Headband", "High-Density Foam Roller", "Insulated Water Bottle 500ml", "Resistance Bands Set", "Speed Jump Rope"]),
            ("cat_accessories", "Accessories", "accessories", ["Printed Silk Scarf", "Adjustable Baseball Cap", "Genuine Leather Belt", "UV400 Designer Sunglasses", "Organic Canvas Tote Bag", "Knitted Wool Beanie"]),
        ]

        col_count = 0
        for cid, title, handle, product_titles in collections_data:
            # Check if a collection with this (shop_id, collection_id) already exists
            existing = await session.execute(
                sa.select(CollectionData).where(
                    CollectionData.shop_id == SHOP_ID,
                    CollectionData.collection_id == cid,
                )
            )
            if existing.scalar_one_or_none():
                continue
            collection = CollectionData(
                shop_id=SHOP_ID,
                collection_id=cid,
                title=title,
                handle=handle,
                description=f"{title} collection",
                product_count=len(product_titles),
                is_automated=False,
                is_active=True,
            )
            session.add(collection)
            col_count += 1

        await session.commit()
        print(f"   ✅ {col_count} collections created")

    print()
    print("=" * 60)
    print("✅ Seed complete!")
    print()
    print("Next:")
    print("  1. Feature computation will detect the new shop and process data")
    print("     (runs automatically every ~5-10 min)")
    print("  2. Check Gorse dashboard at http://localhost:8088 for user/item counts")
    print("  3. Run: uv run python-worker/app/scripts/validation/validate_recommendations.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
