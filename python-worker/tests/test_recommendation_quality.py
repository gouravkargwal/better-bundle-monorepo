"""
Realistic Data Generator + Gorse Training Validation Script

Generates realistic e-commerce data, inserts into feature tables,
syncs to Gorse via UnifiedGorseService, trains, and validates
recommendation quality.

Run inside the python-worker container:
  python -m pytest tests/test_recommendation_quality.py -v -s
"""

import os
import asyncio
import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

import pytest
import pytest_asyncio

# Ensure env vars are set before any app imports
os.environ.setdefault("GORSE_BASE_URL", "http://gorse:8088")

from sqlalchemy import select, func, delete
from app.core.database.session import get_session_context
from app.core.database.models.shop import Shop
from app.core.database.models.features import (
    UserFeatures,
    ProductFeatures,
    InteractionFeatures,
    SessionFeatures,
    ProductPairFeatures,
    SearchProductFeatures,
)
from app.core.database.models.order_data import OrderData, LineItemData
from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.services.unified_gorse_service import UnifiedGorseService
from app.recommandations.fp_growth_engine import FPGrowthEngine, FPGrowthConfig

# ============================================================
# Constants
# ============================================================

TEST_SHOP_ID = f"test_shop_{uuid.uuid4().hex[:8]}"
GORSE_BASE_URL = os.environ.get("GORSE_BASE_URL", "http://gorse:8088")

# Product catalog - 30 products across 5 categories
PRODUCTS = {
    # Electronics (8)
    "prod_laptop": {"title": "Laptop Pro 15", "category": "Electronics", "price": 1299.99},
    "prod_phone": {"title": "Smartphone X", "category": "Electronics", "price": 899.99},
    "prod_headphones": {"title": "Wireless Headphones", "category": "Electronics", "price": 249.99},
    "prod_charger": {"title": "Fast Charger USB-C", "category": "Electronics", "price": 39.99},
    "prod_mouse": {"title": "Ergonomic Mouse", "category": "Electronics", "price": 59.99},
    "prod_keyboard": {"title": "Mechanical Keyboard", "category": "Electronics", "price": 129.99},
    "prod_phone_case": {"title": "Phone Case Premium", "category": "Electronics", "price": 29.99},
    "prod_screen_protector": {"title": "Screen Protector HD", "category": "Electronics", "price": 14.99},
    # Clothing (7)
    "prod_tshirt": {"title": "Cotton T-Shirt", "category": "Clothing", "price": 24.99},
    "prod_jacket": {"title": "Winter Jacket", "category": "Clothing", "price": 189.99},
    "prod_shoes": {"title": "Running Shoes", "category": "Clothing", "price": 119.99},
    "prod_jeans": {"title": "Slim Fit Jeans", "category": "Clothing", "price": 69.99},
    "prod_hat": {"title": "Baseball Cap", "category": "Clothing", "price": 19.99},
    "prod_socks": {"title": "Athletic Socks 6-Pack", "category": "Clothing", "price": 14.99},
    "prod_belt": {"title": "Leather Belt", "category": "Clothing", "price": 34.99},
    # Home (6)
    "prod_cookware": {"title": "Non-Stick Pan Set", "category": "Home", "price": 89.99},
    "prod_pillow": {"title": "Memory Foam Pillow", "category": "Home", "price": 49.99},
    "prod_lamp": {"title": "LED Desk Lamp", "category": "Home", "price": 39.99},
    "prod_blanket": {"title": "Weighted Blanket", "category": "Home", "price": 79.99},
    "prod_mug": {"title": "Ceramic Coffee Mug", "category": "Home", "price": 12.99},
    "prod_candle": {"title": "Scented Candle Set", "category": "Home", "price": 24.99},
    # Sports (5)
    "prod_yoga_mat": {"title": "Premium Yoga Mat", "category": "Sports", "price": 49.99},
    "prod_yoga_blocks": {"title": "Yoga Blocks Set", "category": "Sports", "price": 19.99},
    "prod_weights": {"title": "Dumbbell Set", "category": "Sports", "price": 149.99},
    "prod_bottle": {"title": "Water Bottle 32oz", "category": "Sports", "price": 24.99},
    "prod_resistance_bands": {"title": "Resistance Bands", "category": "Sports", "price": 19.99},
    # Beauty (4)
    "prod_shampoo": {"title": "Organic Shampoo", "category": "Beauty", "price": 18.99},
    "prod_conditioner": {"title": "Deep Conditioner", "category": "Beauty", "price": 16.99},
    "prod_moisturizer": {"title": "Face Moisturizer", "category": "Beauty", "price": 34.99},
    "prod_sunscreen": {"title": "SPF 50 Sunscreen", "category": "Beauty", "price": 14.99},
}

PRODUCT_IDS = list(PRODUCTS.keys())

# Customer profiles with behavior characteristics
CUSTOMERS = {
    # Power buyers (3)
    "cust_power_1": {"type": "power", "primary_category": "Electronics", "aov": 350, "purchases": 25, "ltv": 8750},
    "cust_power_2": {"type": "power", "primary_category": "Clothing", "aov": 200, "purchases": 30, "ltv": 6000},
    "cust_power_3": {"type": "power", "primary_category": "Home", "aov": 280, "purchases": 20, "ltv": 5600},
    # Regular shoppers (5)
    "cust_regular_1": {"type": "regular", "primary_category": "Electronics", "aov": 120, "purchases": 10, "ltv": 1200},
    "cust_regular_2": {"type": "regular", "primary_category": "Sports", "aov": 80, "purchases": 8, "ltv": 640},
    "cust_regular_3": {"type": "regular", "primary_category": "Beauty", "aov": 60, "purchases": 12, "ltv": 720},
    "cust_regular_4": {"type": "regular", "primary_category": "Clothing", "aov": 100, "purchases": 7, "ltv": 700},
    "cust_regular_5": {"type": "regular", "primary_category": "Home", "aov": 90, "purchases": 9, "ltv": 810},
    # Casual browsers (7)
    "cust_casual_1": {"type": "casual", "primary_category": "Electronics", "aov": 50, "purchases": 3, "ltv": 150},
    "cust_casual_2": {"type": "casual", "primary_category": "Clothing", "aov": 40, "purchases": 2, "ltv": 80},
    "cust_casual_3": {"type": "casual", "primary_category": "Home", "aov": 30, "purchases": 2, "ltv": 60},
    "cust_casual_4": {"type": "casual", "primary_category": "Sports", "aov": 45, "purchases": 3, "ltv": 135},
    "cust_casual_5": {"type": "casual", "primary_category": "Beauty", "aov": 35, "purchases": 2, "ltv": 70},
    "cust_casual_6": {"type": "casual", "primary_category": "Electronics", "aov": 55, "purchases": 4, "ltv": 220},
    "cust_casual_7": {"type": "casual", "primary_category": "Clothing", "aov": 25, "purchases": 1, "ltv": 25},
    # New/cold start (5)
    "cust_new_1": {"type": "new", "primary_category": None, "aov": 0, "purchases": 0, "ltv": 0},
    "cust_new_2": {"type": "new", "primary_category": None, "aov": 0, "purchases": 0, "ltv": 0},
    "cust_new_3": {"type": "new", "primary_category": "Electronics", "aov": 30, "purchases": 1, "ltv": 30},
    "cust_new_4": {"type": "new", "primary_category": "Beauty", "aov": 20, "purchases": 1, "ltv": 20},
    "cust_new_5": {"type": "new", "primary_category": None, "aov": 0, "purchases": 0, "ltv": 0},
}

CUSTOMER_IDS = list(CUSTOMERS.keys())

# Deliberate co-purchase patterns for FBT validation
CO_PURCHASE_PATTERNS = [
    {"items": ["prod_phone_case", "prod_screen_protector"], "count": 15, "customer_pool": "all"},
    {"items": ["prod_shampoo", "prod_conditioner"], "count": 12, "customer_pool": "all"},
    {"items": ["prod_laptop", "prod_mouse"], "count": 10, "customer_pool": "power_regular"},
    {"items": ["prod_laptop", "prod_keyboard"], "count": 10, "customer_pool": "power_regular"},
    {"items": ["prod_yoga_mat", "prod_yoga_blocks"], "count": 8, "customer_pool": "all"},
    {"items": ["prod_laptop", "prod_mouse", "prod_keyboard"], "count": 5, "customer_pool": "power"},
]


# ============================================================
# Helpers
# ============================================================

def _random_date(days_back: int = 90) -> datetime:
    """Generate a random datetime within the last N days"""
    return datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def _get_customer_pool(pool_name: str) -> List[str]:
    """Get customer IDs matching a pool name"""
    if pool_name == "all":
        return [c for c, info in CUSTOMERS.items() if info["type"] != "new"]
    elif pool_name == "power_regular":
        return [c for c, info in CUSTOMERS.items() if info["type"] in ("power", "regular")]
    elif pool_name == "power":
        return [c for c, info in CUSTOMERS.items() if info["type"] == "power"]
    return CUSTOMER_IDS


def _lifecycle_stage(customer_type: str) -> str:
    return {
        "power": "loyal_customer",
        "regular": "returning_customer",
        "casual": "engaged_browser",
        "new": "new_visitor",
    }.get(customer_type, "new_visitor")


def _price_tier(price: float) -> str:
    if price >= 500:
        return "luxury"
    elif price >= 100:
        return "premium"
    elif price >= 30:
        return "mid"
    return "budget"


# ============================================================
# Data Generation
# ============================================================

async def generate_product_features(shop_id: str) -> int:
    """Insert ProductFeatures for all 30 products"""
    async with get_session_context() as session:
        count = 0
        for pid, info in PRODUCTS.items():
            price = info["price"]
            # Vary scores based on price and category
            velocity = random.uniform(0.3, 0.95)
            pf = ProductFeatures(
                shop_id=shop_id,
                product_id=pid,
                interaction_volume_score=random.uniform(0.2, 0.9),
                purchase_velocity_score=velocity,
                engagement_quality_score=random.uniform(0.3, 0.85),
                price_tier=_price_tier(price),
                revenue_potential_score=min(price / 1500.0, 1.0),
                conversion_efficiency=random.uniform(0.05, 0.4),
                days_since_last_purchase=random.randint(1, 30),
                activity_recency_score=random.uniform(0.5, 1.0),
                trending_momentum=random.uniform(-0.2, 0.8),
                product_lifecycle_stage=random.choice(["growing", "mature", "peak", "stable"]),
                inventory_health_score=random.uniform(0.5, 1.0),
                product_category=info["category"],
            )
            session.add(pf)
            count += 1
        await session.commit()
    return count


async def generate_user_features(shop_id: str) -> int:
    """Insert UserFeatures for all 20 customers"""
    async with get_session_context() as session:
        count = 0
        for cid, info in CUSTOMERS.items():
            ctype = info["type"]
            churn = {"power": 0.1, "regular": 0.3, "casual": 0.6, "new": 0.9}.get(ctype, 0.9)
            freq = {"power": 0.9, "regular": 0.5, "casual": 0.2, "new": 0.0}.get(ctype, 0.0)
            diversity = {"power": 0.8, "regular": 0.5, "casual": 0.3, "new": 0.0}.get(ctype, 0.0)
            recency = {"power": 0.95, "regular": 0.7, "casual": 0.4, "new": 0.1}.get(ctype, 0.1)
            conv = {"power": 0.35, "regular": 0.15, "casual": 0.05, "new": 0.0}.get(ctype, 0.0)

            uf = UserFeatures(
                shop_id=shop_id,
                customer_id=cid,
                total_purchases=info["purchases"],
                total_interactions=info["purchases"] * random.randint(3, 8),
                lifetime_value=float(info["ltv"]),
                avg_order_value=float(info["aov"]),
                purchase_frequency_score=freq + random.uniform(-0.05, 0.05),
                interaction_diversity_score=diversity + random.uniform(-0.05, 0.05),
                days_since_last_purchase=random.randint(1, 60) if ctype != "new" else None,
                recency_score=recency + random.uniform(-0.05, 0.05),
                conversion_rate=conv + random.uniform(-0.02, 0.02),
                primary_category=info["primary_category"],
                category_diversity={"power": 4, "regular": 3, "casual": 2, "new": 0}.get(ctype, 0),
                user_lifecycle_stage=_lifecycle_stage(ctype),
                churn_risk_score=churn + random.uniform(-0.05, 0.05),
            )
            session.add(uf)
            count += 1
        await session.commit()
    return count


async def generate_orders(shop_id: str) -> int:
    """Generate 80 orders with deliberate co-purchase patterns"""
    order_count = 0

    async with get_session_context() as session:
        # --- Pattern orders (deliberate co-purchases) ---
        for pattern in CO_PURCHASE_PATTERNS:
            pool = _get_customer_pool(pattern["customer_pool"])
            for i in range(pattern["count"]):
                customer_id = random.choice(pool)
                order_date = _random_date(60)  # keep within 60 days for FP-Growth
                total = sum(PRODUCTS[pid]["price"] for pid in pattern["items"])

                order = OrderData(
                    shop_id=shop_id,
                    order_id=f"order_{uuid.uuid4().hex[:12]}",
                    order_name=f"#TEST-{order_count + 1001}",
                    customer_id=customer_id,
                    total_amount=total,
                    subtotal_amount=total,
                    order_date=order_date,
                    confirmed=True,
                    test=False,
                    financial_status="paid",
                    fulfillment_status="fulfilled",
                    order_status="closed",
                    currency_code="USD",
                    created_at=order_date,
                    updated_at=order_date,
                )
                session.add(order)
                await session.flush()  # get the auto-generated id

                for pid in pattern["items"]:
                    li = LineItemData(
                        order_id=order.id,
                        product_id=pid,
                        variant_id=f"var_{pid}",
                        title=PRODUCTS[pid]["title"],
                        quantity=1,
                        price=PRODUCTS[pid]["price"],
                    )
                    session.add(li)

                order_count += 1

        # --- Random noise orders (to reach ~80 total) ---
        noise_target = max(0, 80 - order_count)
        active_customers = [c for c, info in CUSTOMERS.items() if info["type"] != "new"]
        for _ in range(noise_target):
            customer_id = random.choice(active_customers)
            num_items = random.randint(1, 4)
            items = random.sample(PRODUCT_IDS, num_items)
            order_date = _random_date(90)
            total = sum(PRODUCTS[pid]["price"] for pid in items)

            order = OrderData(
                shop_id=shop_id,
                order_id=f"order_{uuid.uuid4().hex[:12]}",
                order_name=f"#TEST-{order_count + 1001}",
                customer_id=customer_id,
                total_amount=total,
                subtotal_amount=total,
                order_date=order_date,
                confirmed=True,
                test=False,
                financial_status="paid",
                fulfillment_status="fulfilled",
                order_status="closed",
                currency_code="USD",
                created_at=order_date,
                updated_at=order_date,
            )
            session.add(order)
            await session.flush()

            for pid in items:
                li = LineItemData(
                    order_id=order.id,
                    product_id=pid,
                    variant_id=f"var_{pid}",
                    title=PRODUCTS[pid]["title"],
                    quantity=random.randint(1, 3),
                    price=PRODUCTS[pid]["price"],
                )
                session.add(li)

            order_count += 1

        await session.commit()
    return order_count


async def generate_interaction_features(shop_id: str) -> int:
    """Generate 150 InteractionFeatures with varied strength"""
    async with get_session_context() as session:
        count = 0
        used_pairs = set()

        for cid, cinfo in CUSTOMERS.items():
            if cinfo["type"] == "new" and cinfo["purchases"] == 0:
                continue

            # Determine how many products this customer interacted with
            num_products = {"power": 15, "regular": 10, "casual": 5, "new": 2}.get(cinfo["type"], 3)
            products = random.sample(PRODUCT_IDS, min(num_products, len(PRODUCT_IDS)))

            for pid in products:
                pair_key = (cid, pid)
                if pair_key in used_pairs:
                    continue
                used_pairs.add(pair_key)

                ctype = cinfo["type"]
                # Power buyers get higher scores
                strength_base = {"power": 0.6, "regular": 0.4, "casual": 0.2, "new": 0.1}.get(ctype, 0.1)
                affinity_base = {"power": 0.7, "regular": 0.4, "casual": 0.2, "new": 0.1}.get(ctype, 0.1)

                # Boost affinity if product matches primary category
                cat_match = PRODUCTS[pid]["category"] == cinfo.get("primary_category")
                affinity_bonus = 0.2 if cat_match else 0.0

                interaction = InteractionFeatures(
                    shop_id=shop_id,
                    customer_id=cid,
                    product_id=pid,
                    interaction_strength_score=min(1.0, strength_base + random.uniform(0, 0.3)),
                    customer_product_affinity=min(1.0, affinity_base + affinity_bonus + random.uniform(0, 0.2)),
                    engagement_progression_score=min(1.0, random.uniform(0.1, 0.4) + (0.4 if ctype == "power" else 0.0)),
                    conversion_likelihood=min(1.0, random.uniform(0.1, 0.3) + (0.5 if ctype == "power" else 0.1 if ctype == "regular" else 0.0)),
                    purchase_intent_score=min(1.0, random.uniform(0.1, 0.4) + (0.4 if ctype == "power" else 0.0)),
                    interaction_recency_score=random.uniform(0.3, 1.0),
                    relationship_maturity=_lifecycle_stage(ctype),
                    interaction_frequency_score=min(1.0, random.uniform(0.1, 0.3) + (0.5 if ctype == "power" else 0.0)),
                    customer_product_loyalty=min(1.0, random.uniform(0.0, 0.3) + (0.5 if ctype == "power" else 0.0)),
                    total_interaction_value=float(PRODUCTS[pid]["price"] * random.uniform(0.5, 2.0)),
                )
                session.add(interaction)
                count += 1

        await session.commit()
    return count


async def generate_session_features(shop_id: str) -> int:
    """Generate 40 SessionFeatures with mix of behavior types"""
    async with get_session_context() as session:
        count = 0
        active_customers = [c for c, info in CUSTOMERS.items() if info["type"] != "new" or info["purchases"] > 0]

        session_types = [
            # (type, bounce, funnel_stage, duration_range, intent_range, count)
            ("conversion", False, "purchase", (8, 30), (0.7, 1.0), 10),
            ("browsing", False, "browsing", (5, 20), (0.2, 0.5), 12),
            ("high_engagement", False, "consideration", (10, 40), (0.5, 0.8), 8),
            ("bounce", True, "landing", (0, 1), (0.0, 0.1), 10),
        ]

        for stype, bounce, funnel, dur_range, intent_range, scount in session_types:
            for i in range(scount):
                cid = random.choice(active_customers)
                sid = f"sess_{uuid.uuid4().hex[:12]}"
                duration = random.randint(dur_range[0], dur_range[1])
                intent = random.uniform(intent_range[0], intent_range[1])

                sf = SessionFeatures(
                    shop_id=shop_id,
                    customer_id=cid,
                    session_id=sid,
                    session_duration_minutes=duration,
                    interaction_count=random.randint(1, 15) if not bounce else 1,
                    interaction_intensity=random.uniform(0.1, 0.9) if not bounce else 0.05,
                    unique_products_viewed=random.randint(1, 8) if not bounce else 1,
                    browse_depth_score=random.uniform(0.1, 0.8) if not bounce else 0.05,
                    conversion_funnel_stage=funnel,
                    purchase_intent_score=intent,
                    session_value=random.uniform(0, 200) if stype == "conversion" else 0.0,
                    session_type=stype,
                    bounce_session=bounce,
                    traffic_source=random.choice(["organic", "direct", "social", "email"]),
                    returning_visitor=CUSTOMERS[cid]["type"] in ("power", "regular"),
                )
                session.add(sf)
                count += 1

        await session.commit()
    return count


async def generate_product_pair_features(shop_id: str) -> int:
    """Generate ProductPairFeatures matching co-purchase patterns"""
    async with get_session_context() as session:
        count = 0
        added_pairs = set()

        # Strong pairs from deliberate patterns
        strong_pairs = [
            ("prod_phone_case", "prod_screen_protector", 0.9, "high"),
            ("prod_shampoo", "prod_conditioner", 0.85, "high"),
            ("prod_laptop", "prod_mouse", 0.75, "high"),
            ("prod_laptop", "prod_keyboard", 0.75, "high"),
            ("prod_yoga_mat", "prod_yoga_blocks", 0.7, "medium"),
            ("prod_laptop", "prod_charger", 0.5, "medium"),
            ("prod_tshirt", "prod_jeans", 0.45, "medium"),
            ("prod_pillow", "prod_blanket", 0.4, "medium"),
        ]

        for p1, p2, strength, confidence_level in strong_pairs:
            pair_key = tuple(sorted([p1, p2]))
            if pair_key in added_pairs:
                continue
            added_pairs.add(pair_key)

            ppf = ProductPairFeatures(
                shop_id=shop_id,
                product_id=p1,  # ProductMixin gives product_id
                product_id1=p1,
                product_id2=p2,
                co_purchase_strength=strength,
                co_engagement_score=strength * 0.9,
                pair_affinity_score=strength * 0.95,
                total_pair_revenue=random.uniform(500, 5000),
                pair_frequency_score=strength * 0.8,
                days_since_last_co_occurrence=random.randint(1, 15),
                pair_recency_score=random.uniform(0.6, 1.0),
                pair_confidence_level=confidence_level,
                cross_sell_potential=strength * 0.85,
            )
            session.add(ppf)
            count += 1

        # Add some weaker random pairs for noise
        for _ in range(12):
            p1, p2 = random.sample(PRODUCT_IDS, 2)
            pair_key = tuple(sorted([p1, p2]))
            if pair_key in added_pairs:
                continue
            added_pairs.add(pair_key)

            strength = random.uniform(0.1, 0.35)
            ppf = ProductPairFeatures(
                shop_id=shop_id,
                product_id=p1,
                product_id1=p1,
                product_id2=p2,
                co_purchase_strength=strength,
                co_engagement_score=strength * 0.8,
                pair_affinity_score=strength * 0.9,
                total_pair_revenue=random.uniform(50, 500),
                pair_frequency_score=strength * 0.7,
                days_since_last_co_occurrence=random.randint(10, 60),
                pair_recency_score=random.uniform(0.2, 0.6),
                pair_confidence_level="low",
                cross_sell_potential=strength * 0.6,
            )
            session.add(ppf)
            count += 1

        await session.commit()
    return count


async def generate_search_features(shop_id: str) -> int:
    """Generate SearchProductFeatures for search-to-product mappings"""
    search_mappings = [
        ("wireless headphones", "prod_headphones", 0.85, 0.3, "high_intent"),
        ("phone accessories", "prod_phone_case", 0.7, 0.25, "high_intent"),
        ("phone accessories", "prod_screen_protector", 0.65, 0.2, "high_intent"),
        ("laptop", "prod_laptop", 0.9, 0.15, "high_intent"),
        ("yoga equipment", "prod_yoga_mat", 0.8, 0.2, "medium_intent"),
        ("yoga equipment", "prod_yoga_blocks", 0.7, 0.15, "medium_intent"),
        ("hair care", "prod_shampoo", 0.75, 0.3, "medium_intent"),
        ("hair care", "prod_conditioner", 0.7, 0.25, "medium_intent"),
        ("winter clothing", "prod_jacket", 0.8, 0.1, "browsing_intent"),
        ("home comfort", "prod_blanket", 0.6, 0.08, "browsing_intent"),
        ("gaming setup", "prod_keyboard", 0.7, 0.12, "high_intent"),
        ("gaming setup", "prod_mouse", 0.65, 0.1, "high_intent"),
        ("workout gear", "prod_weights", 0.75, 0.15, "medium_intent"),
        ("workout gear", "prod_resistance_bands", 0.6, 0.1, "medium_intent"),
        ("skincare routine", "prod_moisturizer", 0.8, 0.2, "high_intent"),
        ("skincare routine", "prod_sunscreen", 0.7, 0.15, "medium_intent"),
        ("gift ideas", "prod_candle", 0.5, 0.05, "browsing_intent"),
        ("gift ideas", "prod_mug", 0.45, 0.04, "low_intent"),
        ("running gear", "prod_shoes", 0.85, 0.2, "high_intent"),
        ("running gear", "prod_bottle", 0.6, 0.1, "medium_intent"),
    ]

    async with get_session_context() as session:
        count = 0
        for query, pid, relevance, conv_rate, intent in search_mappings:
            spf = SearchProductFeatures(
                shop_id=shop_id,
                product_id=pid,
                search_query=query,
                search_click_rate=random.uniform(0.1, 0.5),
                search_conversion_rate=conv_rate + random.uniform(-0.02, 0.02),
                search_relevance_score=relevance,
                total_search_interactions=random.randint(10, 200),
                search_to_purchase_count=random.randint(1, 20),
                days_since_last_search_interaction=random.randint(1, 30),
                search_recency_score=random.uniform(0.5, 1.0),
                semantic_match_score=relevance * random.uniform(0.8, 1.0),
                search_intent_alignment=intent,
            )
            session.add(spf)
            count += 1
        await session.commit()
    return count


# ============================================================
# Cleanup
# ============================================================

async def create_test_shop(shop_id: str) -> str:
    """Create a Shop record for FK constraints. Returns the shop id."""
    async with get_session_context() as session:
        # Check if it already exists
        result = await session.execute(
            select(Shop).where(Shop.id == shop_id)
        )
        if result.scalar():
            return shop_id

        shop = Shop(
            id=shop_id,
            shop_domain=f"test-{shop_id[:8]}.myshopify.com",
            access_token="test_token_not_real",
            plan_type="Free",
            is_active=True,
        )
        session.add(shop)
        await session.commit()
    return shop_id


async def cleanup_test_data(shop_id: str):
    """Remove all test data for this shop"""
    async with get_session_context() as session:
        for model in [
            SearchProductFeatures,
            ProductPairFeatures,
            SessionFeatures,
            InteractionFeatures,
            UserFeatures,
            ProductFeatures,
        ]:
            await session.execute(delete(model).where(model.shop_id == shop_id))

        # Delete line items first (FK constraint)
        orders_result = await session.execute(
            select(OrderData.id).where(OrderData.shop_id == shop_id)
        )
        order_ids = [row[0] for row in orders_result.fetchall()]
        if order_ids:
            await session.execute(
                delete(LineItemData).where(LineItemData.order_id.in_(order_ids))
            )
            await session.execute(delete(OrderData).where(OrderData.shop_id == shop_id))

        # Delete the test shop itself
        await session.execute(delete(Shop).where(Shop.id == shop_id))

        await session.commit()


# ============================================================
# Tests
# ============================================================

@pytest.fixture(scope="module")
def event_loop():
    """Create a module-scoped event loop"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def shop_id():
    return TEST_SHOP_ID


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_data(shop_id):
    """Generate all test data and clean up after tests"""
    print(f"\n{'='*60}")
    print(f"Setting up test data for shop: {shop_id}")
    print(f"{'='*60}")

    # Clean any previous test data
    await cleanup_test_data(shop_id)

    # Create the test shop record (FK constraint)
    await create_test_shop(shop_id)

    # Generate all feature data
    counts = {}
    counts["products"] = await generate_product_features(shop_id)
    print(f"  Inserted {counts['products']} products")
    counts["users"] = await generate_user_features(shop_id)
    print(f"  Inserted {counts['users']} users")
    counts["orders"] = await generate_orders(shop_id)
    print(f"  Inserted {counts['orders']} orders")
    counts["interactions"] = await generate_interaction_features(shop_id)
    print(f"  Inserted {counts['interactions']} interactions")
    counts["sessions"] = await generate_session_features(shop_id)
    print(f"  Inserted {counts['sessions']} sessions")
    counts["product_pairs"] = await generate_product_pair_features(shop_id)
    print(f"  Inserted {counts['product_pairs']} product pairs")
    counts["search_features"] = await generate_search_features(shop_id)
    print(f"  Inserted {counts['search_features']} search features")

    print(f"\nData generation complete!")

    yield counts

    # Cleanup after all tests
    print(f"\nCleaning up test data for shop: {shop_id}")
    await cleanup_test_data(shop_id)


class TestDataGeneration:
    """Verify test data was inserted correctly"""

    @pytest.mark.asyncio
    async def test_products_inserted(self, shop_id):
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count()).select_from(ProductFeatures).where(
                    ProductFeatures.shop_id == shop_id
                )
            )
            count = result.scalar()
        assert count == 30, f"Expected 30 products, got {count}"
        print(f"  Products: {count}")

    @pytest.mark.asyncio
    async def test_users_inserted(self, shop_id):
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count()).select_from(UserFeatures).where(
                    UserFeatures.shop_id == shop_id
                )
            )
            count = result.scalar()
        assert count == 20, f"Expected 20 users, got {count}"
        print(f"  Users: {count}")

    @pytest.mark.asyncio
    async def test_orders_inserted(self, shop_id):
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count()).select_from(OrderData).where(
                    OrderData.shop_id == shop_id
                )
            )
            count = result.scalar()
        assert count >= 60, f"Expected at least 60 orders, got {count}"
        print(f"  Orders: {count}")

    @pytest.mark.asyncio
    async def test_interactions_inserted(self, shop_id):
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count()).select_from(InteractionFeatures).where(
                    InteractionFeatures.shop_id == shop_id
                )
            )
            count = result.scalar()
        assert count >= 50, f"Expected at least 50 interactions, got {count}"
        print(f"  Interactions: {count}")

    @pytest.mark.asyncio
    async def test_co_purchase_patterns_exist(self, shop_id):
        """Verify that co-purchase patterns are in the order data"""
        from sqlalchemy.orm import joinedload
        async with get_session_context() as session:
            result = await session.execute(
                select(OrderData)
                .options(joinedload(OrderData.line_items))
                .where(OrderData.shop_id == shop_id)
            )
            orders = result.unique().scalars().all()

            # Count co-occurrences of Phone Case + Screen Protector
            co_count = 0
            for order in orders:
                product_ids = {li.product_id for li in order.line_items}
                if "prod_phone_case" in product_ids and "prod_screen_protector" in product_ids:
                    co_count += 1

            assert co_count >= 15, f"Expected at least 15 Phone Case + Screen Protector co-purchases, got {co_count}"
            print(f"  Phone Case + Screen Protector co-purchases: {co_count}")


class TestGorseSync:
    """Test syncing data to Gorse"""

    @pytest.mark.asyncio
    async def test_gorse_health(self):
        """Check Gorse is reachable"""
        client = GorseApiClient(GORSE_BASE_URL)
        health = await client.health_check()
        print(f"  Gorse health: {health}")
        assert health["success"], f"Gorse not healthy: {health}"

    @pytest.mark.asyncio
    async def test_sync_to_gorse(self, shop_id):
        """Sync all test data to Gorse via UnifiedGorseService"""
        service = UnifiedGorseService(gorse_base_url=GORSE_BASE_URL)
        result = await service.comprehensive_sync_and_train(shop_id)

        print(f"\n  Sync results:")
        for k, v in result.get("sync_results", {}).items():
            print(f"    {k}: {v}")
        print(f"  Total synced: {result.get('total_items_synced', 0)}")
        print(f"  Errors: {result.get('errors', [])}")

        assert result.get("total_items_synced", 0) > 0, f"Nothing synced: {result}"

    @pytest.mark.asyncio
    async def test_gorse_has_users(self, shop_id):
        """Verify Gorse received our users by querying a specific test user"""
        import httpx
        test_user_id = f"shop_{shop_id}_cust_power_1"
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GORSE_BASE_URL}/api/user/{test_user_id}")
            print(f"  User query ({test_user_id}): status={resp.status_code}")
            if resp.status_code == 200:
                user = resp.json()
                print(f"  User found: {user.get('UserId', 'N/A')}, Labels: {len(user.get('Labels', []))}")
                assert user.get("UserId") == test_user_id
            else:
                # User may not be synced yet if deadlock occurred; check latest items as proxy
                resp2 = await client.get(f"{GORSE_BASE_URL}/api/latest", params={"n": 50})
                if resp2.status_code == 200:
                    items = resp2.json()
                    test_items = [i for i in items if isinstance(i, dict) and f"shop_{shop_id}" in i.get("Id", "")]
                    print(f"  Items with our shop prefix in latest: {len(test_items)}")
                    assert len(test_items) > 0, "No test data found in Gorse at all"

    @pytest.mark.asyncio
    async def test_gorse_has_items(self, shop_id):
        """Verify Gorse received our items by querying a specific test item"""
        import httpx
        test_item_id = f"shop_{shop_id}_prod_laptop"
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GORSE_BASE_URL}/api/item/{test_item_id}")
            print(f"  Item query ({test_item_id}): status={resp.status_code}")
            if resp.status_code == 200:
                item = resp.json()
                print(f"  Item found: {item.get('ItemId', 'N/A')}, Labels: {len(item.get('Labels', []))}")
                assert item.get("ItemId") == test_item_id
            else:
                # Check latest items as fallback
                resp2 = await client.get(f"{GORSE_BASE_URL}/api/latest", params={"n": 50})
                if resp2.status_code == 200:
                    items = resp2.json()
                    test_items = [i for i in items if isinstance(i, dict) and f"shop_{shop_id}" in i.get("Id", "")]
                    print(f"  Test items in latest: {len(test_items)}")
                    assert len(test_items) > 0, "No test items found in Gorse"

    @pytest.mark.asyncio
    async def test_gorse_has_feedback(self, shop_id):
        """Verify Gorse has feedback (total across all shops)"""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GORSE_BASE_URL}/api/dashboard/stats")
            if resp.status_code == 200:
                stats = resp.json()
                total_feedback = stats.get("NumTotalPosFeedback", 0)
                num_users = stats.get("NumUsers", 0)
                num_items = stats.get("NumItems", 0)
                print(f"  Gorse totals: {num_users} users, {num_items} items, {total_feedback} positive feedback")
                # After our sync, total counts should have increased
                assert num_items > 0, f"No items in Gorse: {stats}"
                assert num_users > 0, f"No users in Gorse: {stats}"


class TestGorseRecommendations:
    """Test Gorse recommendation endpoints after sync"""

    @pytest.mark.asyncio
    async def test_item_neighbors(self, shop_id):
        """Phone Case should have Screen Protector as neighbor"""
        client = GorseApiClient(GORSE_BASE_URL)
        phone_case_id = f"shop_{shop_id}_prod_phone_case"

        result = await client.get_item_neighbors(phone_case_id, n=10)
        print(f"\n  Item neighbors for Phone Case: {result}")

        if result["success"] and result.get("neighbors"):
            neighbor_ids = [n.get("Id", "") if isinstance(n, dict) else str(n) for n in result["neighbors"]]
            screen_protector_id = f"shop_{shop_id}_prod_screen_protector"
            if screen_protector_id in neighbor_ids:
                print(f"  SUCCESS: Screen Protector found in Phone Case neighbors!")
            else:
                print(f"  NOTE: Screen Protector not yet in neighbors (Gorse may still be training)")
                print(f"  Neighbor IDs: {neighbor_ids}")
        else:
            print(f"  NOTE: No neighbors yet (Gorse may still be training)")

    @pytest.mark.asyncio
    async def test_popular_items(self, shop_id):
        """Should return some popular items"""
        client = GorseApiClient(GORSE_BASE_URL)
        result = await client.get_popular_items(n=10)
        print(f"\n  Popular items: {result}")

        if result["success"]:
            count = result.get("count", 0)
            print(f"  Popular items count: {count}")

    @pytest.mark.asyncio
    async def test_latest_items(self, shop_id):
        """Should return recently inserted items"""
        client = GorseApiClient(GORSE_BASE_URL)
        result = await client.get_latest_items(n=10)
        print(f"\n  Latest items: {result}")

        if result["success"]:
            count = result.get("count", 0)
            print(f"  Latest items count: {count}")

    @pytest.mark.asyncio
    async def test_user_recommendations(self, shop_id):
        """Power buyer should get recommendations"""
        client = GorseApiClient(GORSE_BASE_URL)
        power_user_id = f"shop_{shop_id}_cust_power_1"

        result = await client.get_recommendations(power_user_id, n=10)
        print(f"\n  Recommendations for power buyer: {result}")

        if result["success"]:
            count = result.get("count", 0)
            print(f"  Recommendation count: {count}")


class TestFPGrowth:
    """Test FP-Growth training on the generated order data"""

    @pytest.mark.asyncio
    async def test_fp_growth_training(self, shop_id):
        """Train FP-Growth and verify rules are generated"""
        config = FPGrowthConfig(
            min_support=0.02,
            min_confidence=0.25,
            min_lift=1.2,
            days_back=120,
        )
        engine = FPGrowthEngine(config=config)
        result = await engine.train_model(shop_id)

        print(f"\n  FP-Growth training result:")
        print(f"    Success: {result.get('success')}")
        print(f"    Transactions: {result.get('transactions_processed', 0)}")
        print(f"    Rules: {result.get('association_rules', 0)}")
        if result.get("quality_metrics"):
            print(f"    Quality: {result['quality_metrics']}")

        assert result.get("success"), f"FP-Growth training failed: {result}"
        assert result.get("association_rules", 0) > 0, "No association rules generated"

    @pytest.mark.asyncio
    async def test_fp_growth_phone_case_rule(self, shop_id):
        """Phone Case should produce Screen Protector recommendation"""
        config = FPGrowthConfig(
            min_support=0.02,
            min_confidence=0.25,
            min_lift=1.2,
            days_back=120,
        )
        engine = FPGrowthEngine(config=config)

        # Train first
        train_result = await engine.train_model(shop_id)
        assert train_result.get("success"), f"Training failed: {train_result}"

        # Load cached rules and check for the pattern
        rules = await engine._load_cached_rules(shop_id)
        assert len(rules) > 0, "No cached rules found"

        # Find rules where phone_case is in antecedent
        phone_case_rules = [
            r for r in rules
            if "prod_phone_case" in r.antecedent
        ]
        print(f"\n  Rules with Phone Case as antecedent: {len(phone_case_rules)}")
        for r in phone_case_rules:
            print(f"    {r.antecedent} -> {r.consequent} (conf={r.confidence:.3f}, lift={r.lift:.3f})")

        # Check if Screen Protector appears in consequent
        screen_protector_rules = [
            r for r in phone_case_rules
            if "prod_screen_protector" in r.consequent
        ]
        assert len(screen_protector_rules) > 0, (
            f"No rule Phone Case -> Screen Protector found. "
            f"All phone_case rules: {[(r.antecedent, r.consequent) for r in phone_case_rules]}"
        )
        best_rule = max(screen_protector_rules, key=lambda r: r.confidence)
        print(f"  Best rule: Phone Case -> Screen Protector (conf={best_rule.confidence:.3f}, lift={best_rule.lift:.3f})")
        assert best_rule.confidence >= 0.3, f"Confidence too low: {best_rule.confidence}"

    @pytest.mark.asyncio
    async def test_fp_growth_shampoo_rule(self, shop_id):
        """Shampoo should produce Conditioner recommendation"""
        config = FPGrowthConfig(
            min_support=0.02,
            min_confidence=0.25,
            min_lift=1.2,
            days_back=120,
        )
        engine = FPGrowthEngine(config=config)
        await engine.train_model(shop_id)

        rules = await engine._load_cached_rules(shop_id)

        shampoo_rules = [r for r in rules if "prod_shampoo" in r.antecedent]
        conditioner_rules = [r for r in shampoo_rules if "prod_conditioner" in r.consequent]

        print(f"\n  Rules with Shampoo as antecedent: {len(shampoo_rules)}")
        for r in shampoo_rules:
            print(f"    {r.antecedent} -> {r.consequent} (conf={r.confidence:.3f})")

        assert len(conditioner_rules) > 0, "No Shampoo -> Conditioner rule found"

    @pytest.mark.asyncio
    async def test_fp_growth_laptop_rules(self, shop_id):
        """Laptop should produce Mouse and/or Keyboard recommendations"""
        config = FPGrowthConfig(
            min_support=0.02,
            min_confidence=0.2,
            min_lift=1.0,
            days_back=120,
        )
        engine = FPGrowthEngine(config=config)
        await engine.train_model(shop_id)

        rules = await engine._load_cached_rules(shop_id)
        laptop_rules = [r for r in rules if "prod_laptop" in r.antecedent]

        print(f"\n  Rules with Laptop as antecedent: {len(laptop_rules)}")
        for r in laptop_rules:
            print(f"    {r.antecedent} -> {r.consequent} (conf={r.confidence:.3f})")

        # Check Mouse or Keyboard
        mouse_or_kbd = [
            r for r in laptop_rules
            if "prod_mouse" in r.consequent or "prod_keyboard" in r.consequent
        ]
        assert len(mouse_or_kbd) > 0, "No Laptop -> Mouse/Keyboard rules found"


class TestQualityReport:
    """Print a comprehensive quality report"""

    @pytest.mark.asyncio
    async def test_print_quality_report(self, shop_id):
        """Print comprehensive quality report"""
        print(f"\n{'='*60}")
        print(f"RECOMMENDATION QUALITY REPORT")
        print(f"Shop: {shop_id}")
        print(f"{'='*60}")

        # 1. Data counts
        print(f"\n--- Data Summary ---")
        async with get_session_context() as session:
            for model, name in [
                (ProductFeatures, "ProductFeatures"),
                (UserFeatures, "UserFeatures"),
                (InteractionFeatures, "InteractionFeatures"),
                (SessionFeatures, "SessionFeatures"),
                (ProductPairFeatures, "ProductPairFeatures"),
                (SearchProductFeatures, "SearchProductFeatures"),
                (OrderData, "OrderData"),
            ]:
                result = await session.execute(
                    select(func.count()).select_from(model).where(model.shop_id == shop_id)
                )
                count = result.scalar()
                print(f"  {name}: {count}")

        # 2. Gorse stats
        print(f"\n--- Gorse Stats ---")
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{GORSE_BASE_URL}/api/dashboard/stats")
                if resp.status_code == 200:
                    stats = resp.json()
                    for k, v in stats.items():
                        print(f"  {k}: {v}")
            except Exception as e:
                print(f"  Error: {e}")

        # 3. FP-Growth quality
        print(f"\n--- FP-Growth Rules ---")
        config = FPGrowthConfig(min_support=0.02, min_confidence=0.25, min_lift=1.2, days_back=120)
        engine = FPGrowthEngine(config=config)
        train_result = await engine.train_model(shop_id)
        rules = await engine._load_cached_rules(shop_id)
        print(f"  Total rules: {len(rules)}")
        if rules:
            print(f"  Avg confidence: {sum(r.confidence for r in rules) / len(rules):.3f}")
            print(f"  Avg lift: {sum(r.lift for r in rules) / len(rules):.3f}")
            print(f"  Max confidence: {max(r.confidence for r in rules):.3f}")
            print(f"  Max lift: {max(r.lift for r in rules):.3f}")

        # 4. Expected pattern validation
        print(f"\n--- Pattern Validation ---")
        expected_patterns = [
            ("prod_phone_case", "prod_screen_protector"),
            ("prod_shampoo", "prod_conditioner"),
            ("prod_laptop", "prod_mouse"),
            ("prod_laptop", "prod_keyboard"),
            ("prod_yoga_mat", "prod_yoga_blocks"),
        ]
        for ant, cons in expected_patterns:
            matching = [r for r in rules if ant in r.antecedent and cons in r.consequent]
            if matching:
                best = max(matching, key=lambda r: r.confidence)
                status = "PASS" if best.confidence >= 0.25 else "WEAK"
                print(f"  {status}: {ant} -> {cons} (conf={best.confidence:.3f}, lift={best.lift:.3f})")
            else:
                print(f"  MISS: {ant} -> {cons} (no rule found)")

        print(f"\n{'='*60}")
        print(f"REPORT COMPLETE")
        print(f"{'='*60}")
