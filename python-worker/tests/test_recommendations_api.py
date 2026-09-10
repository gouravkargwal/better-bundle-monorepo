"""
End-to-end contract test for the recommendation API.

Everything else in this suite tests the serve path's decisions in isolation
(ranking, price ceilings, substitute vetoes) against asserted SQL text. This
file tests the one thing none of that can: that a real request against a real
shop's real edges comes back with something a storefront extension can render,
and that the impression rows the billing depends on actually get written.

It needs a live database with a seeded shop, so every test skips rather than
fails when there is nothing installed — a fresh checkout should not show red.

Run with:
    docker compose -f docker-compose.dev.yml exec python-worker \
        python -m pytest tests/test_recommendations_api.py -v
"""

import hashlib
import json
import uuid
from typing import List, Optional

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.api.v1.recommendations import (
    CONTEXT_SURFACE,
    RETURN_LIMIT,
    InvalidInputError,
    ShopNotFoundError,
    fetch_recommendations_logic,
    services,
)
from app.core.database.session import get_transaction_context
from app.shared.helpers import now_utc
from app.recommandations.models import RecommendationRequest
from app.services.holdout_service import INITIAL_HOLDOUT_PERCENT

pytestmark = pytest.mark.asyncio


# A real shopper's User-Agent. Required, not decorative: the serve path treats a
# missing User-Agent as a bot and deliberately writes no impression for one, so
# without this every test below would assert against un-recorded offers.
SHOPPER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Fixtures grounded in whatever is actually seeded
# ---------------------------------------------------------------------------


async def _fetch_one(sql: str, **params):
    async with get_transaction_context() as session:
        return (await session.execute(text(sql), params)).first()


async def _fetch_all(sql: str, **params):
    async with get_transaction_context() as session:
        return (await session.execute(text(sql), params)).all()


@pytest_asyncio.fixture
async def shop():
    """The seeded shop, or skip. Never invent one — the point is real data."""
    row = await _fetch_one(
        "SELECT id, shop_domain, currency_code FROM shops "
        "WHERE is_active = true ORDER BY created_at LIMIT 1"
    )
    if row is None:
        pytest.skip("no installed shop in the database")
    return row


@pytest_asyncio.fixture
async def source_product(shop):
    """A product that genuinely has recommendable edges pointing away from it.

    Picked from the database rather than hardcoded: the seeder generates
    different product ids on every run, so a literal id would rot immediately.
    """
    row = await _fetch_one(
        """
        SELECT e.source_product_id AS product_id, COUNT(*) AS edges
        FROM product_edges e
        JOIN product_data p
          ON p.shop_id = e.shop_id AND p.product_id = e.target_product_id
        WHERE e.shop_id = :shop_id
          AND e.edge_type IN ('complement', 'accessory', 'refill')
          AND p.is_active = true
        GROUP BY e.source_product_id
        ORDER BY edges DESC
        LIMIT 1
        """,
        shop_id=shop.id,
    )
    if row is None:
        pytest.skip("no recommendable edges — run the install pipeline first")
    return row.product_id


def _identity_in_bucket(shop_id: str, want_control: bool, surface: Optional[str] = "phoenix") -> str:
    """An identity that deterministically lands in control, or does not.

    Bucketing is `md5(shop_id:surface:identity) % 100 < holdout_percent`, so the answer
    depends on the shop. Derived at runtime and salted per call so each test
    also gets a distinct cache key — a cached response would skip the
    impression write and make these assertions pass for the wrong reason.
    """
    salt = uuid.uuid4().hex[:8]
    for n in range(2000):
        candidate = f"{salt}-{n}"
        key = f"{shop_id}:{surface}:{candidate}" if surface else f"{shop_id}:{candidate}"
        bucket = (
            int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        )
        if (bucket < INITIAL_HOLDOUT_PERCENT) is want_control:
            return candidate
    raise AssertionError("could not find an identity in the requested bucket")


@pytest_asyncio.fixture(autouse=True)
async def clean_impressions():
    """Delete impressions this test created.

    Serving writes real `offer_impressions` rows — that is the point, since
    the billing depends on them — but it means running this suite against a
    dev database inflates the merchant's impact dashboard with fake traffic.
    One run added 85 impressions and 5 control rows to a store whose genuine
    activity was 27, which would have shown up as revenue-less "offers shown".

    Keyed on time rather than on returned ids, because control rows are never
    returned to the caller and would otherwise be left behind.
    """
    started = now_utc()
    yield
    async with get_transaction_context() as session:
        await session.execute(
            text("DELETE FROM offer_impressions WHERE created_at >= :t"),
            {"t": started},
        )


async def _impressions_for(group_ids: List[str]):
    if not group_ids:
        return []
    return await _fetch_all(
        "SELECT offer_id, is_control, surface, metadata FROM offer_impressions "
        "WHERE impression_group_id = ANY(:gids)",
        gids=group_ids,
    )


# ---------------------------------------------------------------------------
# The happy path: a shopper on a product page gets renderable offers
# ---------------------------------------------------------------------------


async def test_product_page_returns_renderable_recommendations(shop, source_product):
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)

    assert result["count"] > 0, (
        "a product with recommendable edges returned nothing — the serve path "
        "is not reaching product_edges"
    )
    assert result["source"] in {"edges_prior", "edges_observed"}
    assert result["context"] == "product_page"

    for item in result["recommendations"]:
        # The extension renders these four; a missing one is a broken widget.
        assert item.get("id"), "recommendation has no product id"
        assert item.get("title"), f"product {item.get('id')} has no title"
        assert item.get("price") is not None
        # Without this the outcome callback has nothing to report against and
        # the purchase can never be attributed.
        assert item.get("impression_id"), (
            f"product {item.get('id')} has no impression_id — attribution "
            "would be impossible for this offer"
        )


async def test_recommendation_count_respects_the_surface_limit(shop, source_product):
    """Checkout shows 3, a storefront carousel 4. Overshooting breaks layout."""
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
    limit = RETURN_LIMIT[CONTEXT_SURFACE["product_page"]]
    assert result["count"] <= limit


async def test_a_product_is_never_recommended_alongside_itself(shop, source_product):
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
    returned = {str(i["id"]) for i in result["recommendations"]}
    assert str(source_product) not in returned


async def test_every_offer_shown_writes_a_treatment_impression(shop, source_product):
    """The impression row is what makes attributed revenue measurable.

    Asserted against the database, not the response: the response carrying an
    impression_id would still pass if the insert silently failed.
    """
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
    assert result["count"] > 0

    impression_ids = [i["impression_id"] for i in result["recommendations"]]
    rows = await _fetch_all(
        "SELECT id, is_control, surface, offer_id FROM offer_impressions "
        "WHERE id = ANY(:ids)",
        ids=impression_ids,
    )

    assert len(rows) == len(impression_ids), "some impressions were never persisted"
    for row in rows:
        assert row.is_control is False, "a shown offer must not be marked control"
        assert row.surface == "phoenix"


# ---------------------------------------------------------------------------
# Holdout: the counterfactual the billing rests on
# ---------------------------------------------------------------------------


async def test_control_shopper_is_shown_nothing(shop, source_product):
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=True),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)

    assert result["count"] == 0
    assert result["recommendations"] == []
    assert result["source"] == "holdout_control"
    assert result["holdout"]["is_control"] is True


async def test_bucketing_is_stable_for_the_same_shopper(shop, source_product):
    """The same shopper must always get the same arm.

    A shopper who flips between arms pollutes both, and the lift the merchant
    is billed on stops meaning anything.
    """
    identity = _identity_in_bucket(shop.id, want_control=True)
    for _ in range(3):
        request = RecommendationRequest(
            shop_domain=shop.shop_domain,
            context="product_page",
            product_id=source_product,
            user_id=identity,
        )
        result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
        assert result["source"] == "holdout_control"


async def test_anonymous_shopper_is_served_but_flagged_unbucketed(
    shop, source_product
):
    """No stable identity means no experiment arm, but still recommendations.

    Every anonymous shopper would otherwise hash to one bucket: either all are
    held out and the widget never renders, or none are. They are served and
    marked `bucketed: false` so they can be excluded from the lift maths.
    """
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)

    assert result["source"] != "holdout_control"
    if result["count"]:
        rows = await _fetch_all(
            "SELECT metadata FROM offer_impressions WHERE id = ANY(:ids)",
            ids=[i["impression_id"] for i in result["recommendations"]],
        )
        for row in rows:
            assert row.metadata.get("bucketed") is False


# ---------------------------------------------------------------------------
# Merchant surface toggles (Settings): a disabled surface serves nothing
# ---------------------------------------------------------------------------


async def _set_shop_settings(shop_id: str, settings: dict | None):
    # Serialized and cast explicitly. Binding a dict straight into a `text()`
    # statement hands asyncpg's jsonb encoder a dict where it expects a string
    # and it dies with "'dict' object has no attribute 'encode'" — the same
    # trap as `::vector`, where an untyped bind reaches the driver with no idea
    # what to do with it. `None` stays None so the column goes to SQL NULL
    # rather than the JSON value `null`, which is what an unconfigured shop has.
    async with get_transaction_context() as session:
        await session.execute(
            text(
                "UPDATE shops SET settings = CAST(:settings AS jsonb) "
                "WHERE id = :shop_id"
            ),
            {
                "settings": json.dumps(settings) if settings is not None else None,
                "shop_id": shop_id,
            },
        )


async def test_disabled_surface_serves_nothing(shop, source_product):
    """A merchant who toggles a surface off in Settings gets an empty widget,
    with no impression rows and no holdout bucketing — the exact contract the
    extension already handles for the control group."""
    previous = await _fetch_one(
        "SELECT settings FROM shops WHERE id = :shop_id", shop_id=shop.id
    )

    try:
        await _set_shop_settings(
            shop.id, {"surfaces": {"phoenix": False, "mercury": True}}
        )
        request = RecommendationRequest(
            shop_domain=shop.shop_domain,
            context="product_page",  # maps to phoenix
            product_id=source_product,
            user_id=_identity_in_bucket(shop.id, want_control=False),
        )
        result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)

        assert result["count"] == 0
        assert result["recommendations"] == []
        assert result["source"] == "surface_disabled"
        assert result["holdout"]["is_control"] is False
    finally:
        await _set_shop_settings(shop.id, previous.settings if previous else None)


async def test_enabled_surface_still_serves(shop, source_product):
    """A surface not mentioned in settings defaults to on — existing shops
    with no settings column value must behave exactly as before."""
    previous = await _fetch_one(
        "SELECT settings FROM shops WHERE id = :shop_id", shop_id=shop.id
    )

    try:
        await _set_shop_settings(shop.id, {"surfaces": {"mercury": False}})
        request = RecommendationRequest(
            shop_domain=shop.shop_domain,
            context="product_page",
            product_id=source_product,
            user_id=_identity_in_bucket(shop.id, want_control=False),
        )
        result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
        assert result["count"] > 0
    finally:
        await _set_shop_settings(shop.id, previous.settings if previous else None)


async def test_merchant_exclusions_are_never_recommended(shop, source_product):
    """Products a merchant excludes in Settings must not appear, even when the
    edges say they would."""
    # Pick the top target for the source product from the DB directly.
    top_target = await _fetch_one(
        """
        SELECT e.target_product_id AS product_id
        FROM product_edges e
        WHERE e.shop_id = :shop_id AND e.source_product_id = :source
          AND e.edge_type IN ('complement', 'accessory', 'refill')
        ORDER BY e.blended_score DESC
        LIMIT 1
        """,
        shop_id=shop.id,
        source=source_product,
    )
    if top_target is None:
        pytest.skip("no edges from source product — nothing to exclude")

    previous = await _fetch_one(
        "SELECT settings FROM shops WHERE id = :shop_id", shop_id=shop.id
    )

    try:
        await _set_shop_settings(
            shop.id, {"excluded_product_ids": [top_target.product_id]}
        )
        request = RecommendationRequest(
            shop_domain=shop.shop_domain,
            context="product_page",
            product_id=source_product,
            user_id=_identity_in_bucket(shop.id, want_control=False),
        )
        result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
        returned = {str(i["id"]) for i in result["recommendations"]}
        assert str(top_target.product_id) not in returned
    finally:
        await _set_shop_settings(shop.id, previous.settings if previous else None)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


async def test_unknown_context_is_rejected(shop):
    """A context with no extension to render it must fail loudly, not silently."""
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="homepage",  # removed along with the phoenix homepage block
        product_id="anything",
    )
    with pytest.raises(InvalidInputError):
        await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)


async def test_unknown_shop_is_rejected():
    request = RecommendationRequest(
        shop_domain="not-a-real-store.myshopify.com",
        context="product_page",
        product_id="anything",
    )
    with pytest.raises(ShopNotFoundError):
        await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)


async def test_missing_shop_and_user_is_rejected():
    request = RecommendationRequest(context="product_page", product_id="anything")
    with pytest.raises(InvalidInputError):
        await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)


async def test_no_context_products_returns_empty_not_an_error(shop):
    """There is nothing to key an edge lookup on, which is not a failure."""
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
    assert result["count"] == 0
    assert result["source"] == "no_context_products"


async def test_unknown_product_returns_empty_not_an_error(shop):
    """A product with no edges yet — a brand new SKU — must not 500."""
    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=f"does-not-exist-{uuid.uuid4().hex}",
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )

    result = await fetch_recommendations_logic(request, services, user_agent=SHOPPER_UA)
    assert result["count"] == 0
    assert result["source"] in {"no_edges", "all_unavailable"}


# ---------------------------------------------------------------------------
# Traffic that gets recommendations but must not be recorded as an impression
# ---------------------------------------------------------------------------


async def _impression_count(shop_id: str) -> int:
    async with get_transaction_context() as session:
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM offer_impressions WHERE shop_id = :shop_id"
                ),
                {"shop_id": shop_id},
            )
        ).scalar_one()


async def test_bot_is_served_but_writes_no_impression(shop, source_product):
    """A crawler should render a normal page and leave no trace in the metrics.

    Impressions are the denominator of the conversion rate the merchant is
    billed against, so a bot fetch that records one understates the app's lift.
    """
    before = await _impression_count(shop.id)

    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
    )
    result = await fetch_recommendations_logic(
        request,
        services,
        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    )

    assert result["count"] > 0, "a bot should still be served a working widget"
    assert await _impression_count(shop.id) == before, (
        "a bot fetch wrote an offer_impressions row"
    )
    for item in result["recommendations"]:
        assert not item.get("impression_id")


async def test_theme_preview_is_served_but_writes_no_impression(shop, source_product):
    """Same contract for a theme preview: the merchant sees the widget work,
    but their own previewing does not land in their impact dashboard."""
    before = await _impression_count(shop.id)

    request = RecommendationRequest(
        shop_domain=shop.shop_domain,
        context="product_page",
        product_id=source_product,
        user_id=_identity_in_bucket(shop.id, want_control=False),
        preview=True,
    )
    result = await fetch_recommendations_logic(
        request, services, user_agent=SHOPPER_UA
    )

    assert result["count"] > 0
    assert await _impression_count(shop.id) == before, (
        "a theme preview wrote an offer_impressions row"
    )


# ---------------------------------------------------------------------------
# Offers the shopper has already answered are not shown again
# ---------------------------------------------------------------------------


async def _record_impression(shop_id: str, session_id: str, offer_id: str, outcome: str):
    async with get_transaction_context() as session:
        await session.execute(
            text(
                """
                INSERT INTO offer_impressions
                    (id, shop_id, session_id, surface, offer_type, offer_id,
                     is_control, outcome, created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :shop_id, :session_id, 'phoenix',
                     'cross_sell', :offer_id, false, :outcome, now(), now())
                """
            ),
            {
                "shop_id": shop_id,
                "session_id": session_id,
                "offer_id": offer_id,
                "outcome": outcome,
            },
        )


async def test_declined_offer_is_never_shown_again(shop):
    """A decline is the clearest signal we get, and we were ignoring it.

    Real data showed one offer declined once on apollo and then shown seven
    more times to the same shopper.
    """
    session_id = f"test-{uuid.uuid4().hex}"
    await _record_impression(shop.id, session_id, "111111", "declined")

    async with get_transaction_context() as session:
        excluded = await services.exclusion.get_impression_exclusions(
            session, shop.id, session_id=session_id
        )

    assert "111111" in excluded


async def test_accepted_offer_is_never_shown_again(shop):
    """An accept means they own it. The purchase-history exclusions only catch
    this once the order lands, which is far too late inside one session."""
    session_id = f"test-{uuid.uuid4().hex}"
    await _record_impression(shop.id, session_id, "222222", "accepted")

    async with get_transaction_context() as session:
        excluded = await services.exclusion.get_impression_exclusions(
            session, shop.id, session_id=session_id
        )

    assert "222222" in excluded


async def test_offer_is_retired_after_the_impression_cap(shop):
    """Two showings is the cap: one re-ask at a higher-intent surface is fair,
    a third is noise."""
    session_id = f"test-{uuid.uuid4().hex}"

    await _record_impression(shop.id, session_id, "333333", "shown")
    async with get_transaction_context() as session:
        after_one = await services.exclusion.get_impression_exclusions(
            session, shop.id, session_id=session_id
        )
    assert "333333" not in after_one, "retired after a single showing"

    await _record_impression(shop.id, session_id, "333333", "shown")
    async with get_transaction_context() as session:
        after_two = await services.exclusion.get_impression_exclusions(
            session, shop.id, session_id=session_id
        )
    assert "333333" in after_two, "shown twice and still not retired"


async def test_another_shoppers_history_does_not_exclude(shop):
    """Exclusions are per shopper. Keying them any wider would let one
    shopper's decline suppress an offer for everybody else."""
    mine = f"test-{uuid.uuid4().hex}"
    theirs = f"test-{uuid.uuid4().hex}"
    await _record_impression(shop.id, theirs, "444444", "declined")

    async with get_transaction_context() as session:
        excluded = await services.exclusion.get_impression_exclusions(
            session, shop.id, session_id=mine
        )

    assert "444444" not in excluded


async def test_no_identity_excludes_nothing(shop):
    """Mercury impressions carry neither customer_id nor session_id, so there
    is no key to scope an exclusion by. It must return empty rather than
    matching every anonymous row in the shop."""
    async with get_transaction_context() as session:
        excluded = await services.exclusion.get_impression_exclusions(
            session, shop.id
        )

    assert excluded == []
