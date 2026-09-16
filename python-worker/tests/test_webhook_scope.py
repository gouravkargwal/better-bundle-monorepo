"""A webhook must never widen into a full catalog sweep.

inventory_updated arrives with its id under "inventory_items" while the data
type being collected is "products". The lookup asked for "products", got
nothing, and fell through to collecting the entire catalog — for every single
stock change. That is what buried the consumer and exhausted the container.
"""

import asyncio

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService


class RecordingAPI:
    def __init__(self, resolve_to=None):
        self.full_sweeps = 0
        self.targeted_fetches = []
        self._resolve_to = resolve_to or []
        self.resolve_calls = 0

    async def get_product_ids_for_inventory_items(self, shop_domain, ids):
        self.resolve_calls += 1
        return list(self._resolve_to)

    async def get_products(self, shop_domain, limit=None, cursor=None,
                           product_ids=None, **kw):
        if product_ids:
            self.targeted_fetches.append(list(product_ids))
            return {
                "edges": [{"node": {"id": p}} for p in product_ids],
                "page_info": {"has_next_page": False},
            }
        self.full_sweeps += 1
        return {
            "edges": [{"node": {"id": f"bulk{i}"}} for i in range(250)],
            "page_info": {"has_next_page": False},
        }


def build(api):
    svc = ShopifyDataCollectionService.__new__(ShopifyDataCollectionService)
    svc.BATCH_SIZE = 250
    svc.TIMEOUT_SECONDS = 300
    svc.RATE_LIMIT_DELAY = 0
    svc.api_client = api
    svc.DATA_TYPES = {
        "products": {"api": "get_products", "field": "updated_at",
                     "store": "store_products_data"}
    }
    svc.stored = []

    async def _store_data(data_type, data, shop_id, source=None):
        svc.stored.extend(data)

    svc._store_data = _store_data
    return svc


INVENTORY_PAYLOAD = {
    "data_types": ["products"],
    "specific_ids": {"inventory_items": ["49578616586415"]},
    "trigger": "webhook",
}


async def test_inventory_webhook_does_not_sweep_the_catalog():
    api = RecordingAPI(resolve_to=["8700619456687"])
    svc = build(api)

    count = await svc._collect_and_store_type(
        "products", "s.myshopify.com", "shop1", "token",
        specific_ids=None, source="webhook",
        targeted=True, collection_payload=INVENTORY_PAYLOAD,
    )

    assert api.full_sweeps == 0, "an inventory webhook swept the whole catalog"
    assert api.resolve_calls == 1, "inventory item was never resolved"
    assert api.targeted_fetches == [["8700619456687"]], api.targeted_fetches
    assert count == 1, count


async def test_unresolvable_webhook_skips_instead_of_sweeping():
    """If the ids cannot be resolved, do nothing — never sweep."""
    api = RecordingAPI(resolve_to=[])
    svc = build(api)

    count = await svc._collect_and_store_type(
        "products", "s.myshopify.com", "shop1", "token",
        specific_ids=None, source="webhook",
        targeted=True, collection_payload=INVENTORY_PAYLOAD,
    )

    assert api.full_sweeps == 0, "unresolvable webhook fell back to a full sweep"
    assert count == 0, count


async def test_real_backfill_still_sweeps():
    """A genuine backfill must still collect everything."""
    api = RecordingAPI()
    svc = build(api)

    count = await svc._collect_and_store_type(
        "products", "s.myshopify.com", "shop1", "token",
        specific_ids=None, source="backfill",
        targeted=False, collection_payload={"data_types": ["products"]},
    )

    assert api.full_sweeps == 1, "a backfill stopped collecting the catalog"
    assert count == 250, count


async def main():
    await test_inventory_webhook_does_not_sweep_the_catalog()
    await test_unresolvable_webhook_skips_instead_of_sweeping()
    await test_real_backfill_still_sweeps()
    print("webhook scope checks passed")


if __name__ == "__main__":
    asyncio.run(main())
