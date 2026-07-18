"""
Validate Gorse recommendations against seeded test data.

Reads seeded products/customers from PostgreSQL, calls Gorse's recommendation API,
and checks if recommendations match expected preference patterns.

Usage:
  uv run python-worker/app/scripts/validation/validate_recommendations.py
"""

import asyncio
import os
import sys
from collections import Counter

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.config.settings import settings
from app.core.database.session import get_session_context
from app.core.database.models.product_data import ProductData

SHOP_ID = "validation_test_shop"
GORSE_BASE_URL = settings.ml.GORSE_BASE_URL
GORSE_API_KEY = settings.ml.GORSE_API_KEY

EXPECTED_PREFERENCES = {
    "alice_power": {"name": "Alice (Power Electronics Buyer)", "main_cat": "electronics", "min_pct": 30},
    "bob_budget": {"name": "Bob (Budget Home Buyer)", "main_cat": "home_garden", "min_pct": 30},
    "carol_fashion": {"name": "Carol (Fashion Enthusiast)", "main_cat": "clothing", "min_pct": 30},
    "dave_fitness": {"name": "Dave (Fitness Fan)", "main_cat": "sports_fitness", "min_pct": 30},
}


async def load_products():
    async with get_session_context() as session:
        import sqlalchemy as sa
        stmt = sa.select(ProductData).where(ProductData.shop_id == SHOP_ID)
        result = await session.execute(stmt)
        return {
            row.product_id: {
                "title": row.title,
                "cat": (row.product_type or "unknown")
                .lower()
                .replace(" & ", "_")
                .replace(" ", "_"),
            }
            for row in result.scalars().all()
        }


def resolve(item_id, products: dict) -> dict:
    # /api/recommend returns plain ID strings; /api/latest and
    # /api/non-personalized/* return {"Id": ..., "Score": ...} objects.
    if isinstance(item_id, dict):
        item_id = item_id.get("Id", "")
    prefix = f"shop_{SHOP_ID}_"
    pid = item_id[len(prefix):] if item_id.startswith(prefix) else item_id
    return products.get(pid, {"title": item_id, "cat": "unknown"})


async def validate():
    print("=" * 70)
    print("🔍 Gorse Recommendation Validation")
    print("=" * 70)

    products = await load_products()
    print(f"\n📦 {len(products)} products loaded")

    async with httpx.AsyncClient(timeout=15.0) as client:
        headers = {"X-API-Key": GORSE_API_KEY} if GORSE_API_KEY else {}

        # Health check
        r = await client.get(f"{GORSE_BASE_URL}/api/health/ready", headers=headers)
        if r.status_code != 200:
            print(f"❌ Gorse not ready: {r.status_code}")
            return
        print("✅ Gorse healthy")

        # Items count (paginated envelope: {"Cursor": ..., "Items": [...]})
        r = await client.get(f"{GORSE_BASE_URL}/api/items", params={"n": 1000}, headers=headers)
        items_count = len(r.json().get("Items", [])) if r.status_code == 200 else 0
        print(f"✅ {items_count} items in Gorse")

        # Validate each customer
        print()
        results = []
        for cid, prefs in EXPECTED_PREFERENCES.items():
            uid = f"shop_{SHOP_ID}_{cid}"
            print(f"\n👤 {prefs['name']} ({uid})")

            r = await client.get(f"{GORSE_BASE_URL}/api/recommend/{uid}", params={"n": 10}, headers=headers)
            if r.status_code != 200:
                print(f"   ⚠️  HTTP {r.status_code}")
                results.append("no_data")
                continue

            recs = r.json()
            if not isinstance(recs, list) or not recs:
                print(f"   ⏳ No recommendations yet")
                results.append("no_data")
                continue

            cats = Counter()
            for item_id in recs:
                info = resolve(item_id, products)
                cats[info["cat"]] += 1
                print(f"   • {info['title']}  [{info['cat']}]")

            main_pct = (cats.get(prefs["main_cat"], 0) / len(recs)) * 100
            top_cat = cats.most_common(1)[0][0] if cats else "?"
            print(f"   {prefs['main_cat']}: {main_pct:.0f}%  (need ≥ {prefs['min_pct']}%)")

            if main_pct >= prefs["min_pct"]:
                print(f"   ✅ PASS")
                results.append("pass")
            elif cats:
                print(f"   ⚠️  WEAK (top: {top_cat})")
                results.append("weak")
            else:
                results.append("no_data")

        # Popular items
        print(f"\n{'─' * 70}")
        r = await client.get(
            f"{GORSE_BASE_URL}/api/non-personalized/popular",
            params={"n": 5},
            headers=headers,
        )
        if r.status_code == 200:
            popular = r.json()
            titles = [resolve(i, products)["title"] for i in popular[:5]]
            print(f"🔥 Popular: {', '.join(titles)}")

        # Latest items
        r = await client.get(f"{GORSE_BASE_URL}/api/latest", params={"n": 5}, headers=headers)
        if r.status_code == 200:
            latest = r.json()
            titles = [resolve(i, products)["title"] for i in latest[:5]]
            print(f"🆕 Latest: {', '.join(titles)}")

        # Summary
        print(f"\n{'=' * 70}")
        passed = results.count("pass")
        weak = results.count("weak")
        no_data = results.count("no_data")
        print(f"📋 {passed}✅ {weak}⚠️  {no_data}⏳  / {len(results)}")
        if no_data == len(results):
            print("\n💡 Pipeline hasn't synced yet. Force sync:")
            print("   curl -X POST http://python-worker:8000/api/v1/gorse/sync/validation_test_shop")
            print("   Then wait ~5 min and retry.")


if __name__ == "__main__":
    asyncio.run(validate())
