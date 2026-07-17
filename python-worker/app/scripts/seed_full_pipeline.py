#!/usr/bin/env python3
"""
End-to-end TFRS test-data pipeline: creates real products/customers/orders in
a Shopify dev store, mirrors them into the local ProductData/CustomerData/
OrderData/LineItemData tables (no need to wait on the Kafka data-collection
consumer), then seeds the behavioral signal (UserSession/UserInteraction/
PurchaseAttribution) TFRS actually trains on.

Requires the app to already be installed on the target shop (a row in
`shops` for shop_domain) — this script writes to that shop's tables, it does
not create the shop/session itself.

Usage:
    export SHOP_DOMAIN=better-bundle-dev.myshopify.com
    export ACCESS_TOKEN=shpat_...
    python app/scripts/seed_full_pipeline.py
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select

from app.core.database.session import get_transaction_context
from app.core.database.models import Shop, ProductData, CustomerData, OrderData, LineItemData
from app.shared.helpers import now_utc

from app.scripts.seed_shopify_graphql import ShopifyGraphQLSeeder
from app.scripts.seed_tfrs_training_data import run as seed_interactions


async def _get_shop_id(shop_domain: str) -> str:
    async with get_transaction_context() as session:
        result = await session.execute(
            select(Shop).where(Shop.shop_domain == shop_domain)
        )
        shop = result.scalar_one_or_none()
        if not shop:
            raise SystemExit(
                f"No shop row for {shop_domain}. Install the app on this store first "
                "(the shop/session must already exist)."
            )
        return shop.id


async def mirror_into_db(
    shop_id: str,
    created_products: Dict[str, Dict[str, Any]],
    created_customers: Dict[str, Dict[str, Any]],
    created_orders: Dict[str, Dict[str, Any]],
) -> None:
    """Write the just-created Shopify data into the local canonical tables,
    matching exactly what the real data-collection consumer would produce."""
    async with get_transaction_context() as session:
        for p in created_products.values():
            session.add(
                ProductData(
                    shop_id=shop_id,
                    product_id=p["id"],
                    title=p["title"],
                    handle=p["handle"],
                    description=p.get("description", ""),
                    product_type=p.get("product_type", ""),
                    vendor=p.get("vendor", ""),
                    tags=p.get("tags", []),
                    status="ACTIVE",
                    total_inventory=p.get("total_inventory", 0),
                    price=p.get("price", 0.0),
                    images=p.get("images", []),
                    is_active=True,
                )
            )

        customer_totals: Dict[str, Dict[str, float]] = {
            c["id"]: {"total_spent": 0.0, "order_count": 0}
            for c in created_customers.values()
        }
        for o in created_orders.values():
            customer_id = o.get("customer_id")
            if customer_id in customer_totals:
                customer_totals[customer_id]["total_spent"] += float(o["totalPrice"])
                customer_totals[customer_id]["order_count"] += 1

        for c in created_customers.values():
            totals = customer_totals.get(c["id"], {"total_spent": 0.0, "order_count": 0})
            session.add(
                CustomerData(
                    shop_id=shop_id,
                    customer_id=c["id"],
                    first_name=c.get("first_name"),
                    last_name=c.get("last_name"),
                    tags=c.get("tags", []),
                    total_spent=totals["total_spent"],
                    order_count=totals["order_count"],
                    verified_email=False,
                    is_active=True,
                )
            )

        now = now_utc()
        for o in created_orders.values():
            order_row = OrderData(
                shop_id=shop_id,
                order_id=o["id"],
                order_name=o["name"],
                customer_id=o.get("customer_id"),
                total_amount=float(o["totalPrice"]),
                subtotal_amount=float(o["totalPrice"]),
                order_date=now,
                confirmed=True,
                test=False,
                financial_status=(o.get("financialStatus") or "paid").lower(),
                order_status="open",
                currency_code="USD",
            )
            session.add(order_row)
            await session.flush()  # need order_row.id for line item FK

            for li in o.get("line_items", []):
                session.add(
                    LineItemData(
                        order_id=order_row.id,
                        product_id=li["product_id"],
                        variant_id=li["variant_id"],
                        quantity=li["quantity"],
                        price=li["price"],
                    )
                )

        await session.commit()

    print(
        f"✅ Mirrored into DB: {len(created_products)} products, "
        f"{len(created_customers)} customers, {len(created_orders)} orders"
    )


async def run(shop_domain: str, access_token: str) -> None:
    shop_id = await _get_shop_id(shop_domain)

    print(f"🚀 Creating real store data on {shop_domain}...")
    seeder = ShopifyGraphQLSeeder(shop_domain, access_token)
    await seeder.create_products()
    await seeder.create_customers()
    await seeder.create_collections()
    await seeder.create_orders()

    await mirror_into_db(
        shop_id, seeder.created_products, seeder.created_customers, seeder.created_orders
    )

    print("\n🎭 Seeding behavioral training data (sessions/interactions/attributions)...")
    await seed_interactions(shop_domain)


if __name__ == "__main__":
    domain = os.environ.get("SHOP_DOMAIN") or os.environ.get("SHOPIFY_SHOP_DOMAIN")
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("SHOPIFY_ACCESS_TOKEN")
    if not domain or not token:
        raise SystemExit("Set SHOP_DOMAIN and ACCESS_TOKEN")
    asyncio.run(run(domain, token))
