"""Known-answer tests for the incrementality statistics.

These are hand-computable cases with values worked out independently of the
implementation, which is the point: the code they replaced returned
`pValue = 0.01` as a literal, and no test could have caught that because there
was nothing to compare against.

Pure functions, no database, no fixtures.
"""

import math
import random

from app.core.stats import (
    Z_95,
    bootstrap_mean_diff,
    normal_cdf,
    two_proportion_z_test,
)


# ---------------------------------------------------------------------------
# Normal CDF
# ---------------------------------------------------------------------------


def test_normal_cdf_known_values():
    assert abs(normal_cdf(0.0) - 0.5) < 1e-12
    assert abs(normal_cdf(Z_95) - 0.975) < 1e-9
    assert abs(normal_cdf(-Z_95) - 0.025) < 1e-9
    assert abs(normal_cdf(1.0) - 0.8413447460685429) < 1e-12


def test_normal_cdf_is_symmetric():
    for x in (0.3, 1.0, 2.5, 4.0):
        assert abs((normal_cdf(x) + normal_cdf(-x)) - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# Two-proportion z-test
# ---------------------------------------------------------------------------


def test_two_proportion_known_answer():
    """12% vs 10% on 10,000 each.

    Worked by hand:
        p̂_t = 0.12, p̂_c = 0.10, p̄ = 0.11
        SE₀  = sqrt(0.11 · 0.89 · (1/10000 + 1/10000)) = 0.00442493...
        z    = 0.02 / 0.00442493 = 4.5198...
    """
    r = two_proportion_z_test(1200, 10000, 1000, 10000)

    assert abs(r.treatment_rate - 0.12) < 1e-12
    assert abs(r.control_rate - 0.10) < 1e-12
    assert abs(r.absolute_diff - 0.02) < 1e-12
    assert r.z is not None and abs(r.z - 4.5198) < 1e-3
    assert r.p_value is not None and r.p_value < 1e-5

    # Relative lift is 0.12/0.10 - 1 = 20%.
    assert r.relative_diff is not None and abs(r.relative_diff - 0.20) < 1e-12
    # A real effect: the interval must exclude zero.
    assert r.relative_diff_lower is not None and r.relative_diff_lower > 0


def test_two_proportion_no_effect_is_not_significant():
    """Identical rates must not produce significance."""
    r = two_proportion_z_test(1000, 10000, 1000, 10000)

    assert r.z is not None and abs(r.z) < 1e-9
    assert r.p_value is not None and r.p_value > 0.99
    assert r.relative_diff is not None and abs(r.relative_diff) < 1e-12
    # The interval must straddle zero.
    assert r.relative_diff_lower is not None and r.relative_diff_lower < 0
    assert r.relative_diff_upper is not None and r.relative_diff_upper > 0


def test_relative_interval_is_asymmetric_and_above_minus_one():
    """The log-ratio delta method's whole purpose.

    A ratio cannot fall below -100%, and its interval is not symmetric. A naive
    `ratio ± z·SE` interval gets both wrong.
    """
    r = two_proportion_z_test(120, 1000, 100, 1000)

    assert r.relative_diff_lower is not None and r.relative_diff_lower > -1.0
    below = r.relative_diff - r.relative_diff_lower
    above = r.relative_diff_upper - r.relative_diff
    assert above > below, "log-ratio interval should lean upward"


def test_absolute_interval_uses_the_unpooled_error():
    """The CI must not assume the null hypothesis it is measuring."""
    r = two_proportion_z_test(1200, 10000, 1000, 10000)

    p_t, p_c = 0.12, 0.10
    se_unpooled = math.sqrt(
        p_t * (1 - p_t) / 10000 + p_c * (1 - p_c) / 10000
    )
    expected_lower = 0.02 - Z_95 * se_unpooled

    assert r.absolute_diff_lower is not None
    assert abs(r.absolute_diff_lower - expected_lower) < 1e-12


def test_two_proportion_zero_control_converters_does_not_raise():
    """The ordinary early-life state: control arm exists but nobody bought.

    Must degrade to None rather than dividing by zero or taking ln(0).
    """
    r = two_proportion_z_test(50, 1000, 0, 1000)

    assert r.relative_diff is None
    assert r.relative_diff_lower is None
    assert r.control_rate == 0.0
    # The absolute difference is still well defined.
    assert abs(r.absolute_diff - 0.05) < 1e-12


def test_two_proportion_empty_arm_does_not_raise():
    r = two_proportion_z_test(0, 0, 0, 0)
    assert r.z is None and r.p_value is None and r.relative_diff is None


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def _revenue_arm(n: int, converters: int, mean_order: float, seed: int):
    """Zero-inflated revenue: mostly non-buyers, a few heavy-tailed orders."""
    rng = random.Random(seed)
    values = [0.0] * (n - converters)
    for _ in range(converters):
        # Lognormal-ish: a long right tail, which is the whole reason a t-test
        # is inappropriate here.
        values.append(mean_order * math.exp(rng.gauss(0, 0.6)) / math.exp(0.18))
    rng.shuffle(values)
    return values


def test_bootstrap_recovers_a_known_lift():
    """Construct a true +5.00 per shopper and check we find it."""
    control = _revenue_arm(5000, 250, 80.0, seed=1)
    # Same generator, plus a constructed uplift spread over every shopper.
    treatment = [v + 5.0 for v in _revenue_arm(5000, 250, 80.0, seed=2)]

    r = bootstrap_mean_diff(treatment, control, seed=7)

    assert r.delta_lower is not None and r.delta_upper is not None
    assert abs(r.delta - 5.0) < 1.5, f"delta {r.delta} should be near 5.0"
    assert r.delta_lower < 5.0 < r.delta_upper, "CI must contain the true lift"
    assert r.delta_lower > 0, "a real lift's interval must exclude zero"
    assert r.p_value is not None and r.p_value < 0.05


def test_bootstrap_finds_no_lift_when_there_is_none():
    """Guards against a bootstrap that manufactures significance."""
    control = _revenue_arm(5000, 250, 80.0, seed=11)
    treatment = _revenue_arm(5000, 250, 80.0, seed=12)

    r = bootstrap_mean_diff(treatment, control, seed=7)

    assert r.delta_lower is not None and r.delta_upper is not None
    assert r.delta_lower < 0 < r.delta_upper, "CI must straddle zero"
    assert r.p_value is not None and r.p_value > 0.05


def test_bootstrap_is_deterministic():
    """A confidence bound that moves between page loads reads as a bug."""
    t = _revenue_arm(2000, 100, 60.0, seed=3)
    c = _revenue_arm(2000, 100, 60.0, seed=4)

    a = bootstrap_mean_diff(t, c, seed=42)
    b = bootstrap_mean_diff(t, c, seed=42)

    assert a.delta_lower == b.delta_lower
    assert a.delta_upper == b.delta_upper
    assert a.p_value == b.p_value


def test_bootstrap_p_value_is_floored_at_resolution():
    """Zero crossings out of B samples means p < 1/B, not p = 0."""
    control = [0.0] * 1000
    treatment = [50.0] * 1000

    r = bootstrap_mean_diff(treatment, control, iterations=500, seed=1)

    assert r.p_value is not None
    assert r.p_value >= 1.0 / 500
    assert r.p_value > 0.0


def test_bootstrap_empty_arm_does_not_raise():
    r = bootstrap_mean_diff([], [1.0, 2.0], seed=1)
    assert r.delta_lower is None and r.p_value is None
    assert r.iterations == 0


def test_bootstrap_handles_an_all_zero_control():
    """Common early on: control shoppers exist, none of them bought."""
    r = bootstrap_mean_diff([0.0] * 900 + [100.0] * 100, [0.0] * 1000, seed=5)

    assert r.control_mean == 0.0
    assert r.delta > 0
    assert r.delta_lower is not None and r.delta_lower > 0
