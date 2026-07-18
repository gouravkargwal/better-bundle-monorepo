"""
Seed interaction data (sessions, events, purchase attributions) for validation.

Creates realistic browsing sessions with known preference patterns so the
feature computation pipeline can produce meaningful interaction/session features.

Tables seeded:
  - user_sessions: browsing sessions per customer
  - user_interactions: individual events within sessions
  - purchase_attributions: links sessions to completed purchases

Run:
  uv run python-worker/app/scripts/validation/seed_interactions.py
"""

import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.database.session import get_session_context
from app.core.database.models.shop import Shop
from app.core.database.models.customer_data import CustomerData
from app.core.database.models.product_data import ProductData
from app.core.database.models.order_data import OrderData
from app.core.database.models.user_session import UserSession
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.purchase_attribution import PurchaseAttribution

SHOP_ID = "validation_test_shop"

# ── Customer interaction profiles ──────────────────────────────────────────
# (customer_id, main_category_filter, secondary_category_filter, num_sessions)
PROFILES = [
    ("alice_power", "electronics", "accessories", 5),
    ("bob_budget", "home_garden", "sports", 3),
    ("carol_fashion", "clothing", "accessories", 4),
    ("dave_fitness", "sports", "electronics", 3),
    ("eve_mixed", None, None, 6),  # buys from all
]

# ── Session templates ──────────────────────────────────────────────────────
# Each template is a list of (interaction_type, count) tuples describing a session flow.
# The feature pipeline uses these to compute InteractionFeatures and SessionFeatures.

SESSION_TEMPLATES = {
    "deep_browse": [  # High-engagement session → "high_engagement_session"
        ("product_viewed", 4),
        ("cart_viewed", 1),
        ("product_added_to_cart", 2),
        ("checkout_started", 1),
        ("checkout_completed", 1),
    ],
    "browse_and_bounce": [  # Low-engagement → "bounce"
        ("product_viewed", 1),
    ],
    "cart_abandon": [  # Added to cart but left → "checkout_started" (read)
        ("product_viewed", 2),
        ("product_added_to_cart", 2),
        ("cart_viewed", 1),
    ],
    "recommendation_click": [  # Clicked a recommendation
        ("recommendation_viewed", 1),
        ("recommendation_clicked", 1),
        ("product_viewed", 2),
        ("recommendation_add_to_cart", 1),
    ],
    "search_and_purchase": [  # Search-driven purchase
        ("search_submitted", 1),
        ("product_viewed", 3),
        ("product_added_to_cart", 1),
        ("checkout_started", 1),
        ("checkout_completed", 1),
    ],
    "return_visit": [  # Came back to a product, purchased
        ("product_viewed", 1),
        ("recommendation_viewed", 1),
        ("product_added_to_cart", 1),
        ("checkout_started", 1),
        ("checkout_completed", 1),
    ],
    "decline_session": [  # User dismissed recommendations
        ("recommendation_viewed", 1),
        ("recommendation_declined", 3),  # Matches RecommendationDeclinedAdapter
        ("product_viewed", 1),
    ],
}


def pick_products(category_filter: str | None, cat_map: dict, count: int) -> list[dict]:
    """Pick random products, optionally filtered by category."""
    if category_filter is None:
        all_products = [p for items in cat_map.values() for p in items]
        return random.sample(all_products, min(count, len(all_products)))
    items = cat_map.get(category_filter, [])
    return random.sample(items, min(count, len(items)))


async def seed_interactions():
    print("=" * 60)
    print("Seeding interaction data for recommendation validation")
    print("=" * 60)

    async with get_session_context() as session:
        # ── Verify shop exists ────────────────────────────────────────────
        shop = await session.get(Shop, SHOP_ID)
        if not shop:
            print("❌ Shop not found. Run seed_shop.py first.")
            return

        # ── Load products grouped by category ─────────────────────────────
        import sqlalchemy as sa
        prod_result = await session.execute(
            sa.select(ProductData).where(ProductData.shop_id == SHOP_ID)
        )
        products = prod_result.scalars().all()
        if not products:
            print("❌ No products found. Run seed_test_data.py first.")
            return

        cat_map: dict[str, list[dict]] = {}
        for p in products:
            cat = (p.product_type or "unknown").lower().replace(" & ", "_").replace(" ", "_")
            cat_map.setdefault(cat, []).append({
                "product_id": p.product_id,
                "title": p.title,
                "price": p.price,
            })

        # ── Load customers ────────────────────────────────────────────────
        cust_result = await session.execute(
            sa.select(CustomerData).where(CustomerData.shop_id == SHOP_ID)
        )
        customers = {c.customer_id: c for c in cust_result.scalars().all()}

        # ── Load existing orders (to create purchase attributions) ────────
        from sqlalchemy.orm import selectinload
        order_result = await session.execute(
            sa.select(OrderData)
            .options(selectinload(OrderData.line_items))
            .where(OrderData.shop_id == SHOP_ID)
        )
        orders = list(order_result.scalars().all())
        orders_by_customer: dict[str, list] = {}
        for o in orders:
            orders_by_customer.setdefault(o.customer_id, []).append(o)

        # ── Orders already attributed in a prior run (order_ids are
        # deterministic, so reruns must skip these or violate the unique
        # (shop_id, order_id) constraint on purchase_attributions) ─────────
        already_attributed_result = await session.execute(
            sa.select(PurchaseAttribution.order_id).where(
                PurchaseAttribution.shop_id == SHOP_ID
            )
        )
        already_attributed_order_ids = {row[0] for row in already_attributed_result.all()}

        # ── Seed interactions per customer ────────────────────────────────
        total_sessions = 0
        total_interactions = 0
        total_attributions = 0

        for cid, main_cat, sec_cat, num_sessions in PROFILES:
            customer = customers.get(cid)
            if not customer:
                continue

            print(f"\n👤 {cid} ({customer.first_name} {customer.last_name})")
            attributed_order_ids = set(already_attributed_order_ids)  # one attribution per order (unique shop_id+order_id)

            # Skip customers who already have their target session count from a prior run
            existing_session_count = (await session.execute(
                sa.select(sa.func.count()).select_from(UserSession).where(
                    UserSession.shop_id == SHOP_ID,
                    UserSession.customer_id == cid,
                )
            )).scalar() or 0
            if existing_session_count >= num_sessions:
                print(f"   → already has {existing_session_count} sessions, skipping")
                continue

            # Resolve category filter keys
            main_key = main_cat.lower().replace(" & ", "_").replace(" ", "_") if main_cat else None
            sec_key = sec_cat.lower().replace(" & ", "_").replace(" ", "_") if sec_cat else None

            session_count = 0
            for s in range(existing_session_count, num_sessions):
                session_id = f"session_{cid}_{s}_{uuid4().hex[:8]}"

                # Pick session type based on position
                if s == 0:
                    template_name = "deep_browse"
                elif s == 1:
                    template_name = random.choice(["search_and_purchase", "recommendation_click"])
                elif s == 2:
                    template_name = "cart_abandon"
                else:
                    template_name = random.choice(["deep_browse", "return_visit", "browse_and_bounce"])

                template = SESSION_TEMPLATES[template_name]
                session_time = datetime.now(timezone.utc) - timedelta(
                    days=random.randint(0, 14),
                    hours=random.randint(0, 23),
                )

                # Pick category for this session (80% main, 20% secondary)
                if main_key and random.random() < 0.8:
                    session_cat = main_key
                elif sec_key:
                    session_cat = sec_key
                else:
                    session_cat = random.choice(list(cat_map.keys()))

                # Estimate total interactions
                total_ev = sum(c for _, c in template)

                # Create session
                user_session = UserSession(
                    shop_id=SHOP_ID,
                    customer_id=cid,
                    browser_session_id=f"browser_{session_id}",
                    status="active",
                    total_interactions=total_ev,
                    last_active=session_time + timedelta(minutes=random.randint(5, 30)),
                    expires_at=session_time + timedelta(hours=4),
                    referrer=random.choice(["direct", "google", "shopify_search", "email", "social"]),
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                )
                session.add(user_session)
                total_sessions += 1
                session_count += 1

                # Create interactions within this session
                item_pool = pick_products(session_cat, cat_map, 8)
                if not item_pool:
                    item_pool = pick_products(None, cat_map, 8)

                ev_idx = 0
                checkout_completed_ev = None

                for ev_type, ev_count in template:
                    for _ in range(ev_count):
                        product = random.choice(item_pool) if item_pool else None
                        meta = {}
                        if product and ev_type in ("product_viewed", "product_added_to_cart",
                                                    "product_removed_from_cart", "recommendation_clicked",
                                                    "recommendation_add_to_cart", "recommendation_declined"):
                            meta = {
                                "product_id": product["product_id"],
                                "product_title": product["title"],
                                "category": main_cat or "mixed",
                                "price": str(product["price"]),
                                "url": f"/products/{product['product_id']}",
                            }
                        elif ev_type == "search_submitted":
                            meta = {
                                "search_query": random.choice([
                                    "gift", "best seller", "new arrivals",
                                    main_cat or "sale", "under $50",
                                ]),
                                "results_count": random.randint(3, 20),
                            }
                        elif ev_type == "recommendation_viewed":
                            meta = {
                                "widget_type": random.choice(["similar", "popular", "recent"]),
                                "items_shown": random.randint(4, 10),
                            }
                        elif ev_type == "recommendation_declined":
                            meta = {
                                "data": {
                                    "product": {
                                        "id": product["product_id"] if product else "",
                                        "title": product["title"] if product else "",
                                        "price": product["price"] if product else 0,
                                        "type": session_cat,
                                    },
                                    "type": "product",
                                    "position": random.randint(1, 5),
                                    "widget": random.choice(["similar", "popular", "recent"]),
                                    "algorithm": random.choice(["collaborative", "embedding", "popular"]),
                                    "confidence": round(random.uniform(0.3, 0.95), 2),
                                    "decline_reason": random.choice([
                                        "user_declined", "not_interested", "already_purchased",
                                    ]),
                                },
                                "session_id": session_id,
                            }

                        interaction = UserInteraction(
                            shop_id=SHOP_ID,
                            session_id=user_session.id,
                            customer_id=cid,
                            extension_type="atlas",
                            interaction_type=ev_type,
                            interaction_metadata=meta,
                            created_at=session_time + timedelta(seconds=ev_idx * random.randint(5, 60)),
                        )
                        session.add(interaction)
                        total_interactions += 1
                        ev_idx += 1

                        if ev_type == "checkout_completed" and product:
                            checkout_completed_ev = {
                                "product": product,
                                "time": interaction.created_at,
                            }

                # Create purchase attribution if session ended in purchase
                # Also link to real order if one exists for this customer
                if checkout_completed_ev and cid in orders_by_customer:
                    matching_orders = [
                        o for o in orders_by_customer[cid]
                        if o.order_id not in attributed_order_ids
                        and checkout_completed_ev["product"]["product_id"] in
                        [li.product_id for li in o.line_items]
                    ]
                    if matching_orders:
                        order = matching_orders[0]
                        attributed_order_ids.add(order.order_id)
                        attribution = PurchaseAttribution(
                            shop_id=SHOP_ID,
                            session_id=user_session.id,
                            customer_id=cid,
                            order_id=order.order_id,
                            contributing_extensions=["atlas"],
                            attribution_weights={"atlas": 1.0},
                            total_revenue=order.total_amount,
                            attributed_revenue={"atlas": order.total_amount},
                            total_interactions=total_ev,
                            interactions_by_extension={"atlas": total_ev},
                            purchase_at=checkout_completed_ev["time"],
                            attribution_algorithm="multi_touch",
                            attribution_metadata={"test": True},
                        )
                        session.add(attribution)
                        total_attributions += 1

            print(f"   → {session_count} sessions, ~{total_ev * session_count} interactions")

        await session.commit()

    print()
    print("=" * 60)
    print(f"✅ Interaction data seeded!")
    print(f"   • {total_sessions} sessions")
    print(f"   • {total_interactions} interactions")
    print(f"   • {total_attributions} purchase attributions")
    print()
    print("Next:")
    print("  1. Feature computation will process this data (~5-10 min)")
    print("  2. Check Gorse dashboard for updated feedback counts")
    print("  3. Run: uv run python-worker/app/scripts/validation/validate_recommendations.py")
    print("=" * 60)


# Import here to avoid circular imports at module level
from uuid import uuid4

if __name__ == "__main__":
    asyncio.run(seed_interactions())
