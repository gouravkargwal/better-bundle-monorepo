#!/usr/bin/env python3
"""
Seed realistic behavioral training data for TFRS.

Run AFTER:
  1. app/scripts/seed_shopify_graphql.py has created products/customers/orders in Shopify
  2. POST /api/v1/data-collection/trigger has pulled that data into ProductData/
     CustomerData/OrderData/LineItemData

This script does NOT talk to Shopify. It reads the real, already-collected
catalog/customer/order rows for a shop and writes the behavioral signal TFRS
actually trains on:
  - UserSession + UserInteraction rows (product_viewed / product_added_to_cart /
    checkout_started / checkout_completed), clustered by product_type so each
    customer has a believable category affinity instead of random noise
  - PurchaseAttribution rows for every real paid order, so the purchase-weighted
    training-label source (see TfrsTrainer._load_attributions) isn't empty

Co-purchase pairs need no seeding here — TfrsTrainer._load_co_purchases derives
them directly from OrderData/LineItemData for any multi-item paid order.

Usage:
    export SHOP_DOMAIN=better-bundle-dev.myshopify.com
    python app/scripts/seed_tfrs_training_data.py
"""

import asyncio
import os
import random
import sys
from datetime import timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database.session import get_transaction_context
from app.core.database.models import (
    Shop,
    ProductData,
    CustomerData,
    OrderData,
    UserSession,
    UserInteraction,
    PurchaseAttribution,
)
from app.shared.helpers import now_utc

# Interaction types TfrsTrainer._load_interactions actually weighs
# (see app/recommandations/tfrs/features.py build_training_dataset)
VIEW = "product_viewed"
CART = "product_added_to_cart"
CHECKOUT_STARTED = "checkout_started"
CHECKOUT_COMPLETED = "checkout_completed"

CROSS_CATEGORY_VIEW_RATE = 0.2  # some noise so the model isn't purely per-category
EXTENSION_TYPES = ["venus", "atlas"]


async def _get_shop_id(shop_domain: str) -> str:
    async with get_transaction_context() as session:
        result = await session.execute(
            select(Shop).where(Shop.shop_domain == shop_domain)
        )
        shop = result.scalar_one_or_none()
        if not shop:
            raise SystemExit(f"No shop found for domain {shop_domain}")
        return shop.id


async def _load_catalog(shop_id: str):
    async with get_transaction_context() as session:
        products = (
            (
                await session.execute(
                    select(ProductData).where(ProductData.shop_id == shop_id)
                )
            )
            .scalars()
            .all()
        )
        customers = (
            (
                await session.execute(
                    select(CustomerData).where(
                        CustomerData.shop_id == shop_id,
                        CustomerData.is_active == True,
                    )
                )
            )
            .scalars()
            .all()
        )
        orders = (
            (
                await session.execute(
                    select(OrderData)
                    .options(selectinload(OrderData.line_items))
                    .where(
                        OrderData.shop_id == shop_id,
                        OrderData.financial_status == "paid",
                        OrderData.test == False,
                        OrderData.customer_id.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        return products, customers, orders


def _group_by_category(products: List[ProductData]) -> Dict[str, List[str]]:
    categories: Dict[str, List[str]] = {}
    for p in products:
        category = p.product_type or "uncategorized"
        categories.setdefault(category, []).append(p.product_id)
    return categories


def _build_interaction(
    shop_id: str,
    session_id: str,
    customer_id: str,
    interaction_type: str,
    product_id: str,
    created_at,
    order_id: str = None,
    attributed_revenue: float = None,
) -> UserInteraction:
    return UserInteraction(
        shop_id=shop_id,
        customer_id=customer_id,
        session_id=session_id,
        extension_type=random.choice(EXTENSION_TYPES),
        interaction_type=interaction_type,
        interaction_metadata={"productId": product_id},
        order_id=order_id,
        attributed_revenue=attributed_revenue,
        created_at=created_at,
        updated_at=created_at,
    )


async def seed_customer_journey(
    shop_id: str,
    customer: CustomerData,
    affinity_products: List[str],
    all_products: List[str],
    matching_orders: List[OrderData],
    session_ctx,
) -> Dict[str, int]:
    """Generate 1-3 realistic sessions for one customer, biased toward their
    affinity category, and attach any real paid orders as completed checkouts."""
    counts = {"sessions": 0, "interactions": 0, "attributions": 0}
    num_sessions = random.randint(1, 3)

    for session_idx in range(num_sessions):
        days_ago = random.randint(1, 60)
        session_time = now_utc() - timedelta(days=days_ago)

        user_session = UserSession(
            shop_id=shop_id,
            customer_id=customer.customer_id,
            browser_session_id=f"seed_{customer.customer_id}_{session_idx}",
            status="active",
            client_id=f"seed_client_{customer.customer_id}_{session_idx}",
            last_active=session_time,
            extensions_used=["atlas", "venus"],
            total_interactions=0,
            created_at=session_time,
            updated_at=session_time,
        )
        session_ctx.add(user_session)
        await session_ctx.flush()
        counts["sessions"] += 1

        # Browse: mostly affinity category, some cross-category noise
        num_views = random.randint(3, 6)
        viewed_products = []
        for _ in range(num_views):
            pool = (
                all_products
                if random.random() < CROSS_CATEGORY_VIEW_RATE
                else affinity_products
            ) or all_products
            product_id = random.choice(pool)
            viewed_products.append(product_id)
            session_ctx.add(
                _build_interaction(
                    shop_id,
                    user_session.id,
                    customer.customer_id,
                    VIEW,
                    product_id,
                    session_time + timedelta(minutes=len(viewed_products)),
                )
            )
            counts["interactions"] += 1

        # Cart a couple of the viewed products
        cart_candidates = viewed_products[: random.randint(1, min(2, len(viewed_products)))]
        for product_id in cart_candidates:
            session_ctx.add(
                _build_interaction(
                    shop_id,
                    user_session.id,
                    customer.customer_id,
                    CART,
                    product_id,
                    session_time + timedelta(minutes=num_views + 1),
                )
            )
            counts["interactions"] += 1

        # This is the last session: attach a real order if this customer has one
        order = matching_orders[session_idx] if session_idx < len(matching_orders) else None
        if order and cart_candidates:
            checkout_time = session_time + timedelta(minutes=num_views + 5)
            session_ctx.add(
                _build_interaction(
                    shop_id,
                    user_session.id,
                    customer.customer_id,
                    CHECKOUT_STARTED,
                    cart_candidates[0],
                    checkout_time,
                )
            )
            counts["interactions"] += 1

            order_product_ids = [
                li.product_id for li in (order.line_items or []) if li.product_id
            ] or cart_candidates
            per_item_revenue = float(order.total_amount or 0) / max(
                len(order_product_ids), 1
            )
            for product_id in order_product_ids:
                session_ctx.add(
                    _build_interaction(
                        shop_id,
                        user_session.id,
                        customer.customer_id,
                        CHECKOUT_COMPLETED,
                        product_id,
                        checkout_time + timedelta(minutes=1),
                        order_id=order.order_id,
                        attributed_revenue=per_item_revenue,
                    )
                )
                counts["interactions"] += 1

            session_ctx.add(
                PurchaseAttribution(
                    shop_id=shop_id,
                    customer_id=customer.customer_id,
                    session_id=user_session.id,
                    order_id=order.order_id,
                    contributing_extensions=["venus"],
                    attribution_weights={"venus": 1.0},
                    total_revenue=float(order.total_amount or 0),
                    attributed_revenue={"venus": float(order.total_amount or 0)},
                    total_interactions=len(order_product_ids) + 2,
                    interactions_by_extension={"venus": len(order_product_ids) + 2},
                    purchase_at=order.order_date or checkout_time,
                    attribution_algorithm="multi_touch",
                    attribution_metadata={
                        "products": [{"id": pid} for pid in order_product_ids]
                    },
                )
            )
            counts["attributions"] += 1

        user_session.total_interactions = counts["interactions"]

    return counts


async def run(shop_domain: str) -> None:
    shop_id = await _get_shop_id(shop_domain)
    products, customers, orders = await _load_catalog(shop_id)

    if not products or not customers:
        raise SystemExit(
            "No products/customers found. Run seed_shopify_graphql.py and "
            "trigger data collection first (see STORE_DATA_GUIDE.md)."
        )

    print(
        f"📊 Found: {len(products)} products, {len(customers)} customers, "
        f"{len(orders)} paid orders"
    )

    categories = _group_by_category(products)
    category_names = list(categories.keys())
    all_product_ids = [p.product_id for p in products]
    print(f"🏷️  Categories: {', '.join(f'{c}({len(v)})' for c, v in categories.items())}")

    # Real orders per customer, so completed-checkout interactions match real revenue
    orders_by_customer: Dict[str, List[OrderData]] = {}
    for order in orders:
        orders_by_customer.setdefault(order.customer_id, []).append(order)

    totals = {"sessions": 0, "interactions": 0, "attributions": 0}

    async with get_transaction_context() as session_ctx:
        for i, customer in enumerate(customers):
            preferred_category = category_names[i % len(category_names)]
            affinity_products = categories[preferred_category]
            matching_orders = orders_by_customer.get(customer.customer_id, [])

            counts = await seed_customer_journey(
                shop_id,
                customer,
                affinity_products,
                all_product_ids,
                matching_orders,
                session_ctx,
            )
            for key in totals:
                totals[key] += counts[key]

        await session_ctx.commit()

    print("\n✅ Seeding complete:")
    print(f"  Sessions:     {totals['sessions']}")
    print(f"  Interactions: {totals['interactions']}")
    print(f"  Attributions: {totals['attributions']}")
    print(
        "\nNext: run TfrsTrainer.train_for_shop(shop_id) and check the reported "
        "training example count / loss to confirm the model is learning real signal."
    )


if __name__ == "__main__":
    domain = os.environ.get("SHOP_DOMAIN") or os.environ.get("SHOPIFY_SHOP_DOMAIN")
    if not domain:
        raise SystemExit("Set SHOP_DOMAIN to the shop's myshopify.com domain")
    asyncio.run(run(domain))
