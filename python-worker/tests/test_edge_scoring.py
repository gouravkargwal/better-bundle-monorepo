"""
Tests for edge scoring: LLR over co-purchases and the prior/observed blend.

These functions decide which products get shown and what a merchant is billed
for, so the properties are pinned rather than spot-checked.
"""

import pytest

from app.recommandations.edges.scoring import (
    BLEND_FULL_OBSERVATIONS,
    BLEND_MIN_OBSERVATIONS,
    blend,
    log_likelihood_ratio,
    observed_score,
    squash_llr,
)


# ---------------------------------------------------------------------------
# LLR
# ---------------------------------------------------------------------------


def test_llr_is_zero_for_independent_items():
    """Co-occurrence exactly at chance carries no information.

    100 orders with A, 100 with B, 1000 total: A and B co-occur 10 times, which
    is precisely 100*100/1000. Nothing to learn.
    """
    assert log_likelihood_ratio(10, 90, 90, 810) == pytest.approx(0.0, abs=1e-9)


def test_llr_grows_with_association_strength():
    weak = log_likelihood_ratio(12, 88, 88, 812)
    strong = log_likelihood_ratio(60, 40, 40, 860)
    assert strong > weak > 0


def test_llr_is_never_negative():
    """Anti-correlated pairs and rounding error must not produce negatives."""
    for table in [(0, 100, 100, 800), (1, 99, 99, 801), (10, 90, 90, 810)]:
        assert log_likelihood_ratio(*table) >= 0.0


def test_llr_is_symmetric_in_the_two_products():
    """A->B and B->A describe the same co-occurrence; swapping k12/k21 must agree."""
    assert log_likelihood_ratio(30, 20, 70, 880) == pytest.approx(
        log_likelihood_ratio(30, 70, 20, 880)
    )


def test_llr_handles_empty_and_degenerate_tables():
    assert log_likelihood_ratio(0, 0, 0, 0) == pytest.approx(0.0)
    # Every order contains both items: perfectly associated, but no contrast.
    assert log_likelihood_ratio(100, 0, 0, 0) == pytest.approx(0.0)


def test_llr_rewards_scale_at_equal_proportions():
    """The same ratio observed over more orders is stronger evidence."""
    small = log_likelihood_ratio(6, 4, 4, 86)
    large = log_likelihood_ratio(60, 40, 40, 860)
    assert large > small


# ---------------------------------------------------------------------------
# Squash
# ---------------------------------------------------------------------------


def test_squash_maps_into_unit_interval():
    for llr in [0.0, 0.5, 1.0, 10.0, 500.0, 100_000.0]:
        assert 0.0 <= squash_llr(llr) <= 1.0


def test_squash_is_zero_at_zero_and_monotonic():
    assert squash_llr(0.0) == 0.0
    assert squash_llr(-5.0) == 0.0
    values = [squash_llr(x) for x in (1, 5, 20, 100, 1000)]
    assert values == sorted(values)
    assert values[-1] < 1.0  # approaches 1 but never reaches it


# ---------------------------------------------------------------------------
# Blend — the load-bearing behaviour
# ---------------------------------------------------------------------------


def test_a_pair_seen_twice_is_not_trusted_however_high_its_llr():
    """The reason the observation gate exists.

    Two co-purchases in a 5,000-order store produce an LLR that squashes to
    ~0.97 — indistinguishable from a genuine pattern. Without the gate, any
    two customers who happened to buy the same two items would outrank the
    install-day prior.
    """
    noisy = observed_score(2, 1, 1, 5000)
    assert noisy > 0.9, "precondition: rare pairs really do score high"

    prior = 0.30
    assert blend(prior, noisy, observed_count=2) == prior


def test_prior_stands_alone_below_the_minimum():
    for n in range(0, BLEND_MIN_OBSERVATIONS):
        assert blend(0.8, 0.1, n) == 0.8


def test_observed_wins_outright_at_and_above_the_maximum():
    for n in (BLEND_FULL_OBSERVATIONS, BLEND_FULL_OBSERVATIONS + 500):
        assert blend(0.8, 0.1, n) == 0.1


def test_blend_ramps_linearly_between_the_thresholds():
    prior, observed = 1.0, 0.0
    midpoint = (BLEND_MIN_OBSERVATIONS + BLEND_FULL_OBSERVATIONS) // 2
    assert blend(prior, observed, midpoint) == pytest.approx(0.5, abs=0.02)


def test_blend_moves_monotonically_toward_observed_as_evidence_accumulates():
    """No jumps: a merchant watching their widget should not see it lurch."""
    scores = [blend(0.9, 0.1, n) for n in range(0, 60)]
    assert scores == sorted(scores, reverse=True)


def test_blend_clamps_out_of_range_inputs():
    assert blend(1.5, 0.5, 0) == 1.0
    assert blend(-0.5, 0.5, 0) == 0.0
    assert blend(0.5, 99.0, 999) == 1.0
    assert blend(None, 0.4, 0) == 0.0


def test_blend_thresholds_are_overridable_for_tuning():
    """Thresholds are guesses; they must be tunable against real conversion data."""
    assert blend(0.8, 0.2, 10, min_observations=1, full_observations=10) == 0.2
