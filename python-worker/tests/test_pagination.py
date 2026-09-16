"""Check that connection pagination survives both pageInfo spellings.

The regression this guards cost 75% of a catalog: the GraphQL queries alias
pageInfo/hasNextPage/endCursor into snake_case, the readers used camelCase,
and a missed key reads as "no more pages" rather than as an error. Collection
stopped after page one and reported success.
"""

from app.domains.shopify.services.api.base_client import page_info_of


def test_page_info():
    # snake_case, as the queries actually alias it
    assert page_info_of(
        {"page_info": {"has_next_page": True, "end_cursor": "abc"}}
    ) == (True, "abc")

    # camelCase, as a raw un-aliased query would return it
    assert page_info_of(
        {"pageInfo": {"hasNextPage": True, "endCursor": "abc"}}
    ) == (True, "abc")

    # last page
    assert page_info_of({"page_info": {"has_next_page": False}}) == (False, None)

    # A connection with no pageInfo at all must report "no next page" without
    # inventing a cursor.
    assert page_info_of({}) == (False, None)
    assert page_info_of({"edges": []}) == (False, None)


def test_client_propagates_page_info():
    """A processed page must not claim to be the last one.

    Every client rebuilt its result dict and hardcoded has_next_page: False,
    which is what actually truncated the catalog.
    """
    import inspect
    from app.domains.shopify.services.api import (
        product_client,
        order_client,
        customer_client,
        collection_client,
    )

    for mod in (product_client, order_client, customer_client, collection_client):
        src = inspect.getsource(mod)
        # The top-level list method must forward the real page info.
        assert '.get("page_info", {}),' in src, (
            f"{mod.__name__} does not propagate page_info from its list query"
        )


if __name__ == "__main__":
    test_page_info()
    test_client_propagates_page_info()
    print("pagination checks passed")
