"""
Edge scoring: log-likelihood ratio over co-purchases, and the prior/observed blend.

Pure functions, no I/O. Everything here is deterministic and unit-tested, because
these numbers decide which products a merchant's customers get shown and what the
merchant is billed for.

Why LLR instead of support / confidence / lift
----------------------------------------------
- `support` (and FP-Growth's `min_support`) prunes on absolute frequency, which
  discards exactly the long-tail pairs that make a recommendation feel non-obvious.
- `confidence` P(B|A) is biased toward popular consequents: every product looks
  "related" to the store bestseller.
- `lift` explodes on rare items — two co-occurrences of two one-off products can
  outrank a genuine pattern.

LLR asks a different question: how surprised should we be by this co-occurrence,
given how often each item sells on its own? It handles "12 co-occurrences out of
5,000 orders" correctly and needs no per-shop threshold tuning.
"""

import math
from typing import Optional

# Below this many co-purchases the observed rate is noise; trust the prior.
BLEND_MIN_OBSERVATIONS = 5
# Above this the data is genuinely better than any prior.
BLEND_FULL_OBSERVATIONS = 50


def _x_log_x(x: float) -> float:
    """x·ln(x), defined as 0 at x=0 (the limit)."""
    return x * math.log(x) if x > 0 else 0.0


def _entropy(*counts: float) -> float:
    """Shannon entropy of a set of counts, in nats, unnormalised."""
    return _x_log_x(sum(counts)) - sum(_x_log_x(c) for c in counts)


def log_likelihood_ratio(k11: int, k12: int, k21: int, k22: int) -> float:
    """LLR for a 2x2 contingency table of co-occurrence.

    Args:
        k11: orders containing both A and B
        k12: orders containing A but not B
        k21: orders containing B but not A
        k22: orders containing neither

    Returns:
        The LLR statistic, >= 0. Larger means the co-occurrence is less likely
        to be chance.
    """
    row_entropy = _entropy(k11 + k12, k21 + k22)
    col_entropy = _entropy(k11 + k21, k12 + k22)
    mat_entropy = _entropy(k11, k12, k21, k22)
    llr = 2.0 * (row_entropy + col_entropy - mat_entropy)
    # Floating-point error can push a true zero very slightly negative.
    return max(0.0, llr)


def squash_llr(llr: float) -> float:
    """Map an unbounded LLR onto 0..1 so it is comparable with a prior.

    1 - 1/(1+llr) is monotonic, hits 0 at llr=0, and approaches 1 slowly, which
    keeps the interesting range (llr roughly 1..50) spread out instead of
    saturating immediately.
    """
    if llr <= 0:
        return 0.0
    return 1.0 - 1.0 / (1.0 + llr)


def observed_score(k11: int, k12: int, k21: int, k22: int) -> float:
    """Convenience: LLR straight to a 0..1 observed score."""
    return squash_llr(log_likelihood_ratio(k11, k12, k21, k22))


def blend(
    prior_score: float,
    observed_llr: float,
    observed_count: int,
    min_observations: int = BLEND_MIN_OBSERVATIONS,
    full_observations: int = BLEND_FULL_OBSERVATIONS,
) -> float:
    """Combine the install-day prior with what the orders actually show.

    Below `min_observations` we are reading noise, so the prior stands alone.
    Above `full_observations` the observed rate wins outright. Between them the
    weight ramps linearly — a step function makes live recommendations visibly
    jump when a pair crosses the threshold, which merchants notice.

    Both inputs are expected in 0..1 and the result is clamped to 0..1.
    """
    prior = _clamp01(prior_score)
    observed = _clamp01(observed_llr)

    if observed_count < min_observations:
        return prior
    if observed_count >= full_observations:
        return observed

    span = full_observations - min_observations
    weight = (observed_count - min_observations) / span
    return _clamp01((1.0 - weight) * prior + weight * observed)


def _clamp01(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))
