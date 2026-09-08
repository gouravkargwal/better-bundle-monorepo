"""
Tests for the serve path and category resolution.

The SQL needs a live Postgres, so the query text is asserted structurally and
the ranking/filtering decisions are tested directly.
"""

import pytest

from app.recommandations.edges import serving
from app.recommandations.edges.enrichment import ProductEnrichment
from app.recommandations.edges.resolution import CategoryResolver
from app.recommandations.edges.serving import (
    DEFAULT_PRICE_CEILING,
    PRICE_CEILING_BY_SURFACE,
    RECOMMENDABLE,
    expected_value,
    prefer_refills,
    price_ceiling,
)


# ---------------------------------------------------------------------------
# Substitutes must never be shown
# ---------------------------------------------------------------------------


def test_substitutes_are_not_a_recommendable_edge_type():
    """Showing an alternative at the payment step invites a swap.

    A swap costs the merchant the original sale, so this is a revenue bug, not
    a relevance one.
    """
    assert "substitute" not in RECOMMENDABLE
    assert set(RECOMMENDABLE) == {"complement", "accessory", "refill"}


def test_serve_query_vetoes_candidates_that_substitute_cart_items():
    """The veto must check every product in the shopper's context.

    Checking only the edge's own source would let a lookalike through whenever
    it was reached via a different cart item.
    """
    sql = str(serving._CANDIDATES_SQL)
    assert "NOT EXISTS" in sql
    assert "sub.edge_type = 'substitute'" in sql
    assert "sub.source_product_id = ANY(:context_ids)" in sql
    assert "sub.target_product_id = pe.target_product_id" in sql


def test_serve_query_filters_stock_and_active_status():
    sql = str(serving._CANDIDATES_SQL)
    assert "pd.is_active = true" in sql
    # NULL inventory means untracked, which is in stock, not out of it.
    assert "pd.total_inventory IS NULL OR pd.total_inventory > 0" in sql


def test_serve_query_excludes_already_held_products():
    assert "NOT (pe.target_product_id = ANY(:exclude_ids))" in str(
        serving._CANDIDATES_SQL
    )


def test_serve_query_returns_one_row_per_product():
    """A product reachable from two cart items must not appear twice."""
    sql = str(serving._CANDIDATES_SQL)
    assert "DISTINCT ON (pe.target_product_id)" in sql
    assert "ORDER BY pe.target_product_id, pe.blended_score DESC" in sql


# ---------------------------------------------------------------------------
# Price ceilings
# ---------------------------------------------------------------------------


def test_checkout_ceiling_is_tighter_than_post_purchase():
    """Checkout is low-consideration; post-purchase is already paid for."""
    assert PRICE_CEILING_BY_SURFACE["mercury"] < PRICE_CEILING_BY_SURFACE["apollo"]
    assert price_ceiling("mercury", 200) == 50.0
    assert price_ceiling("apollo", 200) == 80.0


def test_unknown_cart_value_disables_the_ceiling_rather_than_zeroing_it():
    """A zero ceiling would filter out everything and show an empty widget."""
    assert price_ceiling("mercury", 0) is None
    assert price_ceiling("mercury", None) is None


def test_unknown_surface_falls_back_to_the_conservative_ceiling():
    assert price_ceiling("something_new", 100) == 100 * DEFAULT_PRICE_CEILING


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_ranking_is_expected_revenue_not_similarity():
    """A weaker match on a pricier item can be worth more, and should win.

    This is what aligns the engine with revenue-share billing.
    """
    strong_cheap = {"blended_score": 0.9, "price": 5.0}
    weak_pricey = {"blended_score": 0.4, "price": 40.0}
    assert expected_value(weak_pricey) > expected_value(strong_cheap)


def test_margin_is_applied_when_available_and_ignored_when_not():
    c = {"blended_score": 0.5, "price": 100.0}
    assert expected_value(c) == 50.0
    assert expected_value(c, margin=0.3) == 15.0
    assert expected_value(c, margin=None) == 50.0


def test_missing_price_or_score_scores_zero_rather_than_crashing():
    assert expected_value({"blended_score": None, "price": 10}) == 0.0
    assert expected_value({"blended_score": 0.5, "price": None}) == 0.0
    assert expected_value({}) == 0.0


def test_post_purchase_prefers_refills_over_accessories_over_complements():
    ordered = prefer_refills(
        [
            {"edge_type": "complement"},
            {"edge_type": "accessory"},
            {"edge_type": "refill"},
        ]
    )
    assert [c["edge_type"] for c in ordered] == ["refill", "accessory", "complement"]


def test_prefer_refills_is_stable_within_an_edge_type():
    """Reordering by type must not scramble the revenue ranking inside a type."""
    items = [
        {"edge_type": "complement", "id": 1},
        {"edge_type": "complement", "id": 2},
        {"edge_type": "refill", "id": 3},
    ]
    assert [c["id"] for c in prefer_refills(items)] == [3, 1, 2]


# ---------------------------------------------------------------------------
# Category resolution -> edges
# ---------------------------------------------------------------------------


def _enrichment(**kw):
    base = {"product_id": "src", "role": "durable", "complement_categories": []}
    return ProductEnrichment.model_validate({**base, **kw})


def test_prior_multiplies_category_strength_by_match_similarity():
    """Both factors matter: a confident category matched to a poor product is
    still a bad recommendation."""
    e = _enrichment(
        complement_categories=[{"category": "yoga blocks", "strength": 0.9}]
    )
    edges = CategoryResolver().build_edges(
        "shop1", e, {"yoga blocks": [("blk1", 0.8)]}
    )
    assert edges[0]["prior_score"] == pytest.approx(0.72)


def test_substitute_category_is_written_as_a_substitute_edge():
    e = _enrichment(substitute_category="exercise mats")
    edges = CategoryResolver().build_edges(
        "shop1", e, {"exercise mats": [("mat2", 0.9)]}
    )
    assert [x["edge_type"] for x in edges] == ["substitute"]


def test_consumables_get_a_refill_self_edge():
    e = _enrichment(role="consumable", replenish_days=45)
    edges = CategoryResolver().build_edges("shop1", e, {})
    refills = [x for x in edges if x["edge_type"] == "refill"]
    assert len(refills) == 1
    assert refills[0]["source_product_id"] == refills[0]["target_product_id"] == "src"


def test_durables_never_get_a_refill_edge():
    """Offering someone a second sofa a fortnight later is the failure this
    prevents; the enrichment validator strips the stray replenish window."""
    e = _enrichment(role="durable", replenish_days=14)
    edges = CategoryResolver().build_edges("shop1", e, {})
    assert not [x for x in edges if x["edge_type"] == "refill"]


def test_duplicate_targets_keep_the_strongest_prior():
    """Two categories can resolve to the same product; the better reason wins."""
    e = _enrichment(
        complement_categories=[
            {"category": "blocks", "strength": 0.9},
            {"category": "props", "strength": 0.4},
        ]
    )
    edges = CategoryResolver().build_edges(
        "shop1", e, {"blocks": [("blk1", 1.0)], "props": [("blk1", 1.0)]}
    )
    assert len(edges) == 1
    assert edges[0]["prior_score"] == pytest.approx(0.9)


def test_prior_scores_stay_within_unit_range():
    e = _enrichment(complement_categories=[{"category": "x y", "strength": 1.0}])
    edges = CategoryResolver().build_edges("shop1", e, {"x y": [("t", 1.0)]})
    assert 0.0 <= edges[0]["prior_score"] <= 1.0


def test_resolution_excludes_the_source_product_from_its_own_matches():
    """Without this a product recommends itself as its own complement."""
    from app.recommandations.edges.resolution import _NEAREST_SQL

    assert "pd.product_id <> :source_product_id" in str(_NEAREST_SQL)


def test_resolution_only_matches_active_products():
    from app.recommandations.edges.resolution import _NEAREST_SQL

    assert "pd.is_active = true" in str(_NEAREST_SQL)
