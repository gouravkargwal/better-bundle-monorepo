"""Cart-recorded click attribution.

The thank-you block and the customer-account block cannot write to a cart —
the order is already placed. All they can do is link out to a product's own
page, where the shopper adds it with the *theme's* button, an add this app
never observes. So no impression id can be stamped on the cart line.

The recommendation link therefore carries the impression id, Phoenix records it
on the cart on arrival, and Shopify promotes it to `order.note_attributes`.
That makes the claim deterministic: it arrives in the order webhook as
server-side fact, needing no session to correlate, no customer, and no time
window.

These tests cover the parsing and the order-contents check, which is what stops
a shopper who followed five recommendations and bought two from having all five
credited. Pure functions, no database.
"""

from decimal import Decimal

import pytest

from app.domains.billing.services.attribution_engine import (
    CLICK_ATTRIBUTE_KEY,
    SESSION_ATTRIBUTE_KEY,
    TRACKING_NAMESPACE,
    AttributionContext,
    AttributionEngine,
)
from app.shared.helpers import now_utc


@pytest.fixture
def engine():
    return AttributionEngine()


def _context(note_attributes=None, metafields=None, session_id=None, products=None):
    return AttributionContext(
        shop_id="shop-1",
        customer_id=None,
        session_id=session_id,
        order_id="order-1",
        purchase_amount=Decimal("100.00"),
        purchase_products=products or [],
        purchase_time=now_utc(),
        order_metafields=metafields,
        order_note_attributes=note_attributes,
    )


# ---------------------------------------------------------------------------
# Parsing the cart attribute
# ---------------------------------------------------------------------------


def test_pairs_are_parsed(engine):
    ctx = _context([{"key": CLICK_ATTRIBUTE_KEY, "value": "impA:100,impB:200"}])
    assert engine._clicked_impressions_from_cart(ctx) == {
        "impA": "100",
        "impB": "200",
    }


def test_name_value_shape_is_accepted(engine):
    """Shopify delivers attributes as {key,value}; some payloads use {name,value}."""
    ctx = _context([{"name": CLICK_ATTRIBUTE_KEY, "value": "impA:100"}])
    assert engine._clicked_impressions_from_cart(ctx) == {"impA": "100"}


def test_malformed_entries_are_skipped_not_fatal(engine):
    """Other apps write to the same cart. A junk value must not kill billing."""
    ctx = _context(
        [{"key": CLICK_ATTRIBUTE_KEY, "value": "impA:100,,garbage,impB:,:300"}]
    )
    assert engine._clicked_impressions_from_cart(ctx) == {"impA": "100"}


def test_absent_attribute_yields_nothing(engine):
    assert engine._clicked_impressions_from_cart(_context([])) == {}
    assert engine._clicked_impressions_from_cart(_context(None)) == {}
    assert engine._clicked_impressions_from_cart(_context([{"junk": 1}])) == {}


def test_non_dict_entries_are_ignored(engine):
    ctx = _context(["not-a-dict", None, {"key": CLICK_ATTRIBUTE_KEY, "value": "a:1"}])
    assert engine._clicked_impressions_from_cart(ctx) == {"a": "1"}


# ---------------------------------------------------------------------------
# Only products actually bought may be credited
# ---------------------------------------------------------------------------


def test_only_purchased_products_are_confirmed(engine):
    """Followed five recommendations, bought two: only two may be credited.

    This is the check that keeps the mechanism honest. The cart attribute is a
    claim made by the browser; the order is the fact. Crediting an impression
    whose product is absent from the order would bill the merchant for a
    purchase that never happened.
    """
    ctx = _context(
        [
            {
                "key": CLICK_ATTRIBUTE_KEY,
                "value": "impA:100,impB:200,impC:300,impD:400,impE:500",
            }
        ],
        products=[{"product_id": "100"}, {"product_id": "300"}],
    )

    pairs = engine._clicked_impressions_from_cart(ctx)
    purchased = {
        str(p.get("product_id") or p.get("id") or "")
        for p in ctx.purchase_products
    }
    confirmed = [imp for imp, pid in pairs.items() if pid in purchased]

    assert sorted(confirmed) == ["impA", "impC"]


def test_nothing_confirmed_when_no_recommendation_was_bought(engine):
    ctx = _context(
        [{"key": CLICK_ATTRIBUTE_KEY, "value": "impA:100"}],
        products=[{"product_id": "999"}],
    )
    pairs = engine._clicked_impressions_from_cart(ctx)
    purchased = {str(p["product_id"]) for p in ctx.purchase_products}
    assert [imp for imp, pid in pairs.items() if pid in purchased] == []


# ---------------------------------------------------------------------------
# Order-side identity, which nothing used to write
# ---------------------------------------------------------------------------


def test_session_comes_from_the_cart_attribute(engine):
    ctx = _context([{"key": SESSION_ATTRIBUTE_KEY, "value": "visitor-9"}])
    assert engine._link_session_id(ctx) == "visitor-9"


def test_cart_attribute_wins_over_metafield_and_caller(engine):
    """The cart attribute is the only one that is actually populated.

    This used to read the `bb_recommendation.session_id` metafield alone, which
    nothing has ever written — Mercury writes extension, context, source and
    products. So it always fell through to `context.session_id`, itself null on
    a guest storefront order, leaving every identity-joined path with nothing
    to join on.
    """
    ctx = _context(
        note_attributes=[{"key": SESSION_ATTRIBUTE_KEY, "value": "from-cart"}],
        metafields=[
            {
                "namespace": TRACKING_NAMESPACE,
                "key": "session_id",
                "value": "from-metafield",
            }
        ],
        session_id="from-caller",
    )
    assert engine._link_session_id(ctx) == "from-cart"


def test_session_falls_back_when_cart_carries_none(engine):
    ctx = _context(
        metafields=[
            {
                "namespace": TRACKING_NAMESPACE,
                "key": "session_id",
                "value": "from-metafield",
            }
        ],
        session_id="from-caller",
    )
    assert engine._link_session_id(ctx) == "from-metafield"

    assert engine._link_session_id(_context(session_id="from-caller")) == "from-caller"
    assert engine._link_session_id(_context()) is None
