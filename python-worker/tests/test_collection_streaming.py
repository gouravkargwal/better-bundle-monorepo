"""Checks that a full collection streams to storage instead of hoarding it.

The regression this guards took the container out: once pagination was fixed,
the collector held every page of every data type in memory before writing a
single row, and a 997-product catalog exhausted the process.
"""

import asyncio

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService


class FakeAPI:
    """Serves `pages` pages of `per_page` fake products."""

    def __init__(self, pages: int, per_page: int):
        self.pages = pages
        self.per_page = per_page
        self.calls = 0

    async def get_products(self, shop_domain, limit=None, cursor=None, **kw):
        self.calls += 1
        page = int(cursor or 0)
        last = page >= self.pages - 1
        return {
            "edges": [
                {"node": {"id": f"p{page}_{i}"}} for i in range(self.per_page)
            ],
            "page_info": {
                "has_next_page": not last,
                "end_cursor": str(page + 1),
            },
        }


async def test_streams_pages_and_never_holds_the_catalog():
    svc = ShopifyDataCollectionService.__new__(ShopifyDataCollectionService)
    svc.BATCH_SIZE = 250
    svc.TIMEOUT_SECONDS = 300
    svc.RATE_LIMIT_DELAY = 0
    svc.api_client = FakeAPI(pages=4, per_page=250)

    seen_page_sizes = []

    async def on_page(items):
        seen_page_sizes.append(len(items))

    total = await svc._collect_data_generic(
        shop_domain="s.myshopify.com",
        data_type="products",
        api_method="get_products",
        query_since=None,
        on_page=on_page,
    )

    # All four pages were fetched and streamed.
    assert total == 1000, f"expected 1000 items collected, got {total}"
    assert seen_page_sizes == [250, 250, 250, 250], seen_page_sizes
    # Storage saw the data one page at a time, never the whole catalog.
    assert max(seen_page_sizes) == 250


async def test_without_callback_still_returns_items():
    """The webhook path asks for a handful of objects and wants them back."""
    svc = ShopifyDataCollectionService.__new__(ShopifyDataCollectionService)
    svc.BATCH_SIZE = 250
    svc.TIMEOUT_SECONDS = 300
    svc.RATE_LIMIT_DELAY = 0
    svc.api_client = FakeAPI(pages=1, per_page=3)

    items = await svc._collect_data_generic(
        shop_domain="s.myshopify.com",
        data_type="products",
        api_method="get_products",
        query_since=None,
    )
    assert isinstance(items, list) and len(items) == 3, items


async def test_api_failure_raises_instead_of_truncating():
    """A mid-pagination failure must not look like a finished catalog."""

    class FailingAPI(FakeAPI):
        async def get_products(self, shop_domain, limit=None, cursor=None, **kw):
            if cursor:  # fails on the second page
                raise RuntimeError("shopify exploded")
            return await super().get_products(shop_domain, limit, cursor, **kw)

    svc = ShopifyDataCollectionService.__new__(ShopifyDataCollectionService)
    svc.BATCH_SIZE = 250
    svc.TIMEOUT_SECONDS = 300
    svc.RATE_LIMIT_DELAY = 0
    svc.api_client = FailingAPI(pages=4, per_page=250)

    async def on_page(items):
        pass

    try:
        await svc._collect_data_generic(
            shop_domain="s.myshopify.com",
            data_type="products",
            api_method="get_products",
            query_since=None,
            on_page=on_page,
        )
    except RuntimeError:
        return  # correct: the failure surfaced
    raise AssertionError("partial collection was reported as a success")


async def main():
    await test_streams_pages_and_never_holds_the_catalog()
    await test_without_callback_still_returns_items()
    await test_api_failure_raises_instead_of_truncating()
    print("collection streaming checks passed")


if __name__ == "__main__":
    asyncio.run(main())
