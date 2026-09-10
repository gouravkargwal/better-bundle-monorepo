"""Statistical tests for incrementality measurement.

Pure functions: no database, no I/O, no dependencies beyond the standard
library. scipy and statsmodels are not installed and are not needed — `math.erf`
gives the normal CDF in closed form, and the bootstrap is a loop.

This exists because the dashboard previously reported `pValue = 0.01` as a
literal and a "95% confidence interval" of `revenue * 0.9` to `revenue * 1.1`.
Every number a merchant is shown about their own money now has a derivation.
"""

import math
import random
from dataclasses import dataclass
from typing import Optional, Sequence

# Φ⁻¹(0.975). Hardcoded because inverting the normal CDF needs a numeric solver
# and the only quantile this module ever wants is the two-sided 95% one.
Z_95 = 1.959963984540054


def normal_cdf(x: float) -> float:
    """Φ(x), the standard normal CDF.

    Φ(x) = ½(1 + erf(x/√2)). `math.erf` is stdlib, so this needs no dependency.
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class ProportionTest:
    """Result of comparing two conversion rates."""

    treatment_rate: float
    control_rate: float
    #: p̂_t - p̂_c, in percentage points as a fraction.
    absolute_diff: float
    absolute_diff_lower: Optional[float]
    absolute_diff_upper: Optional[float]
    #: (p̂_t / p̂_c) - 1. None when the control rate is zero.
    relative_diff: Optional[float]
    relative_diff_lower: Optional[float]
    relative_diff_upper: Optional[float]
    z: Optional[float]
    p_value: Optional[float]


def two_proportion_z_test(
    treatment_converters: int,
    treatment_n: int,
    control_converters: int,
    control_n: int,
) -> ProportionTest:
    """Two-sided two-proportion z-test with confidence intervals.

    The primary test. Conversion is a Bernoulli outcome per shopper, so this is
    exact enough in closed form and needs no resampling.

    Two different standard errors are used on purpose, and conflating them is a
    common error:

    - The **z statistic** uses the *pooled* proportion. Under the null the two
      rates are equal, so the best estimate of that shared rate pools both arms.
    - The **confidence interval** uses the *unpooled* standard error. A CI
      describes the observed difference without assuming the null, so pooling
      there would be assuming the very thing the interval is meant to measure.

    Returns None for the statistics rather than raising when an arm is empty or
    has no converters — that is the ordinary early-life state, not an error, and
    the caller's state machine reports it as insufficient data.
    """
    if treatment_n <= 0 or control_n <= 0:
        return ProportionTest(0.0, 0.0, 0.0, None, None, None, None, None, None, None)

    p_t = treatment_converters / treatment_n
    p_c = control_converters / control_n
    absolute = p_t - p_c

    # Pooled, for the test statistic.
    pooled = (treatment_converters + control_converters) / (treatment_n + control_n)
    se_null = math.sqrt(pooled * (1.0 - pooled) * (1.0 / treatment_n + 1.0 / control_n))

    z: Optional[float] = None
    p_value: Optional[float] = None
    if se_null > 0:
        z = absolute / se_null
        p_value = 2.0 * (1.0 - normal_cdf(abs(z)))

    # Unpooled, for the interval on the absolute difference.
    se_obs = math.sqrt(
        p_t * (1.0 - p_t) / treatment_n + p_c * (1.0 - p_c) / control_n
    )
    abs_lower = absolute - Z_95 * se_obs
    abs_upper = absolute + Z_95 * se_obs

    # Relative lift via the log-ratio delta method. Building the interval on
    # ln(p_t/p_c) and exponentiating keeps it strictly above -100% and lets it
    # be asymmetric, which a naive p_t/p_c ± z·SE interval does neither.
    rel: Optional[float] = None
    rel_lower: Optional[float] = None
    rel_upper: Optional[float] = None
    if p_c > 0 and p_t > 0:
        rel = (p_t / p_c) - 1.0
        se_log = math.sqrt(
            (1.0 - p_t) / (p_t * treatment_n) + (1.0 - p_c) / (p_c * control_n)
        )
        theta = math.log(p_t / p_c)
        rel_lower = math.exp(theta - Z_95 * se_log) - 1.0
        rel_upper = math.exp(theta + Z_95 * se_log) - 1.0

    return ProportionTest(
        treatment_rate=p_t,
        control_rate=p_c,
        absolute_diff=absolute,
        absolute_diff_lower=abs_lower,
        absolute_diff_upper=abs_upper,
        relative_diff=rel,
        relative_diff_lower=rel_lower,
        relative_diff_upper=rel_upper,
        z=z,
        p_value=p_value,
    )


@dataclass(frozen=True)
class BootstrapResult:
    """Result of comparing two mean-revenue-per-shopper values."""

    treatment_mean: float
    control_mean: float
    delta: float
    delta_lower: Optional[float]
    delta_upper: Optional[float]
    p_value: Optional[float]
    iterations: int


# Enough for a stable 95% percentile interval; the third decimal of the bound
# stops moving well before this. Raising it buys precision nobody reads.
DEFAULT_ITERATIONS = 1000

# ponytail: resampling is O(iterations × n). Arms are capped by the caller
# before they get here so a large shop cannot blow the dashboard's 4s proxy
# timeout. Subsampling only widens the interval — it errs toward NOT claiming
# significance, which is the safe direction. Move to a nightly precompute if
# shops outgrow it.
MAX_ARM_SIZE = 20_000


def bootstrap_mean_diff(
    treatment: Sequence[float],
    control: Sequence[float],
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = 0,
) -> BootstrapResult:
    """Non-parametric bootstrap of the difference in mean revenue per shopper.

    Why not a t-test: revenue per shopper is zero-inflated — typically 95-99% of
    shoppers buy nothing, so the vector is mostly exact zeros — with a heavy
    right tail where one order can be fifty times the median. The effective
    sample size is therefore the *converter* count, not the shopper count, and
    at a few hundred converters the sampling distribution of the mean is nowhere
    near normal. A symmetric t-interval under-covers, and a single outlier order
    can move p across 0.05. Welch's t additionally assumes comparable finite
    variances, which two arms with different tail mass do not have.

    The bootstrap assumes nothing about the distribution and its percentile
    interval reproduces the real asymmetry.

    Seeded so a merchant reloading the dashboard sees the same interval twice.
    An unstable confidence bound reads as a bug, and rightly so.
    """
    t = list(treatment)[:MAX_ARM_SIZE]
    c = list(control)[:MAX_ARM_SIZE]

    if not t or not c:
        return BootstrapResult(
            treatment_mean=(sum(t) / len(t)) if t else 0.0,
            control_mean=(sum(c) / len(c)) if c else 0.0,
            delta=0.0,
            delta_lower=None,
            delta_upper=None,
            p_value=None,
            iterations=0,
        )

    t_mean = sum(t) / len(t)
    c_mean = sum(c) / len(c)
    delta = t_mean - c_mean

    rng = random.Random(seed)
    deltas = []
    n_t, n_c = len(t), len(c)
    for _ in range(iterations):
        t_star = sum(rng.choices(t, k=n_t)) / n_t
        c_star = sum(rng.choices(c, k=n_c)) / n_c
        deltas.append(t_star - c_star)
    deltas.sort()

    lower = _percentile(deltas, 2.5)
    upper = _percentile(deltas, 97.5)

    # Two-sided bootstrap p: how often the resampled difference lands on the
    # other side of zero. Floored at 1/iterations because zero crossings out of
    # B samples means "p < 1/B", not "p = 0" — the resolution is bounded by the
    # number of iterations and reporting 0.0 would overstate it.
    at_or_below = sum(1 for d in deltas if d <= 0.0)
    at_or_above = sum(1 for d in deltas if d >= 0.0)
    p_value = max(
        2.0 * min(at_or_below, at_or_above) / iterations, 1.0 / iterations
    )
    p_value = min(p_value, 1.0)

    return BootstrapResult(
        treatment_mean=t_mean,
        control_mean=c_mean,
        delta=delta,
        delta_lower=lower,
        delta_upper=upper,
        p_value=p_value,
        iterations=iterations,
    )


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile of an already-sorted sequence."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[int(rank)]
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight
