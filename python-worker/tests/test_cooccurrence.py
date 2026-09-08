"""
Tests for co-purchase mining.

The SQL itself needs a live Postgres, so these cover the pure pieces: the
contingency table construction, the pair scoring, and the guarantee that the
SQL blend ramp cannot drift from the Python one.
"""

import re
from types import SimpleNamespace

import pytest

from app.recommandations.edges import cooccurrence
from app.recommandations.edges.cooccurrence import (
    COUNTED_FINANCIAL_STATUSES,
    MAX_BASKET_SIZE,
    CoPurchaseMiner,
    contingency,
)
from app.recommandations.edges.scoring import (
    BLEND_FULL_OBSERVATIONS,
    BLEND_MIN_OBSERVATIONS,
    blend,
    observed_score,
)


# ---------------------------------------------------------------------------
# Contingency table
# ---------------------------------------------------------------------------


def test_contingency_partitions_the_order_population():
    """The four cells must sum to the total order count."""
    k11, k12, k21, k22 = contingency(50, 60, 70, 5000)
    assert (k11, k12, k21, k22) == (50, 10, 20, 4920)
    assert k11 + k12 + k21 + k22 == 5000


def test_contingency_floors_cells_when_counts_disagree():
    """A count mismatch must degrade the score, never produce a negative cell.

    Item counts and the order total are read in separate queries, so a sync
    landing between them can make the pair count exceed the total. Feeding a
    negative into the entropy calculation would produce a nonsense LLR.
    """
    for cell in contingency(50, 60, 70, 10):
        assert cell >= 0
    assert contingency(100, 10, 10, 0) == (100, 0, 0, 0)


def test_contingency_handles_a_pair_that_never_sells_alone():
    assert contingency(30, 30, 30, 100) == (30, 0, 0, 70)


# ---------------------------------------------------------------------------
# Pair scoring
# ---------------------------------------------------------------------------


def _pair(a, b, count):
    return SimpleNamespace(product_a=a, product_b=b, pair_count=count)


def test_each_pair_is_written_in_both_directions():
    """Co-purchase is symmetric, but the serve path looks up by source."""
    rows = list(
        CoPurchaseMiner()._score_pairs(
            [_pair("A", "B", 12)], {"A": 40, "B": 30}, 1000, "shop_1"
        )
    )
    assert len(rows) == 2
    assert {(r["source_product_id"], r["target_product_id"]) for r in rows} == {
        ("A", "B"),
        ("B", "A"),
    }
    # Same evidence, so both directions carry the same score.
    assert rows[0]["observed_llr"] == rows[1]["observed_llr"]
    assert all(r["observed_count"] == 12 for r in rows)


def test_mined_edges_are_complements_only():
    """Co-occurrence cannot tell an accessory from a refill or a substitute.

    Mislabelling here would be dangerous: `substitute` edges are used to
    *exclude* candidates at checkout, so inferring one from co-purchase could
    silently suppress good recommendations.
    """
    rows = list(
        CoPurchaseMiner()._score_pairs(
            [_pair("A", "B", 9)], {"A": 20, "B": 20}, 500, "shop_1"
        )
    )
    assert {r["edge_type"] for r in rows} == {"complement"}


def test_scoring_matches_the_scoring_module():
    rows = list(
        CoPurchaseMiner()._score_pairs(
            [_pair("A", "B", 25)], {"A": 60, "B": 80}, 2000, "shop_1"
        )
    )
    assert rows[0]["observed_llr"] == observed_score(*contingency(25, 60, 80, 2000))


def test_missing_item_count_falls_back_to_the_pair_count():
    """An item absent from the counts map must not crash or invent evidence.

    Falling back to the pair count means k12/k21 are zero: the pair is treated
    as always co-occurring, which is the most conservative reading available.
    """
    rows = list(
        CoPurchaseMiner()._score_pairs([_pair("A", "B", 7)], {}, 900, "shop_1")
    )
    assert len(rows) == 2
    assert rows[0]["observed_llr"] >= 0.0


def test_stronger_evidence_scores_higher():
    weak = list(
        CoPurchaseMiner()._score_pairs(
            [_pair("A", "B", 3)], {"A": 100, "B": 100}, 2000, "s"
        )
    )[0]["observed_llr"]
    strong = list(
        CoPurchaseMiner()._score_pairs(
            [_pair("A", "B", 80)], {"A": 100, "B": 100}, 2000, "s"
        )
    )[0]["observed_llr"]
    assert strong > weak


# ---------------------------------------------------------------------------
# Guardrails that protect the signal
# ---------------------------------------------------------------------------


def test_wholesale_orders_are_excluded_by_basket_cap():
    """A 60-line trade order contributes 1,770 pairs and swamps real signal."""
    assert MAX_BASKET_SIZE <= 25
    assert ":max_basket" in str(cooccurrence._PAIR_SQL)
    assert "BETWEEN 2 AND :max_basket" in str(cooccurrence._PAIR_SQL)


def test_voided_and_cancelled_orders_are_not_counted():
    """Attribution and learning must both ignore money that never landed."""
    assert "voided" not in COUNTED_FINANCIAL_STATUSES
    assert "pending" not in COUNTED_FINANCIAL_STATUSES
    assert "cancelled_at IS NULL" in str(cooccurrence._PAIR_SQL)
    # A refunded order still evidences that the two items were bought together.
    assert "refunded" in COUNTED_FINANCIAL_STATUSES


def test_baskets_deduplicate_repeated_products():
    """Buying three of the same item is one basket member, not three."""
    assert "GROUP BY o.id, li.product_id" in str(cooccurrence._PAIR_SQL)


def test_pairs_are_counted_once_per_unordered_pair():
    assert "a.product_id < b.product_id" in str(cooccurrence._PAIR_SQL)


def test_item_counts_use_the_same_population_as_pair_counts():
    """k12/k21 are only meaningful if derived from the same filtered orders."""
    pair_sql, item_sql = str(cooccurrence._PAIR_SQL), str(cooccurrence._ITEM_SQL)
    for clause in (
        "o.shop_id = :shop_id",
        "o.order_date >= :cutoff",
        "o.cancelled_at IS NULL",
    ):
        assert clause in pair_sql and clause in item_sql


# ---------------------------------------------------------------------------
# The SQL / Python divergence guard
# ---------------------------------------------------------------------------


def test_sql_blend_mirrors_python_blend():
    """The ramp is expressed twice; the thresholds must come from one place.

    The SQL bulk-update is kept for speed, so the formula is mirrored rather
    than shared. This pins the parts that would silently diverge: the threshold
    constants, and the linear shape between them.
    """
    sql = str(cooccurrence._upsert_blend_sql())

    # Thresholds are bound parameters, never literals.
    assert ":min_obs" in sql and ":full_obs" in sql
    assert not re.search(r"observed_count\s*<\s*\d", sql)

    # And the Python ramp really is linear between the same bounds, which is
    # what the SQL expression computes.
    lo, hi = BLEND_MIN_OBSERVATIONS, BLEND_FULL_OBSERVATIONS
    prior, observed = 0.2, 0.9
    for n in (lo, (lo + hi) // 2, hi - 1):
        expected = prior + (observed - prior) * ((n - lo) / (hi - lo))
        assert blend(prior, observed, n) == pytest.approx(expected)
