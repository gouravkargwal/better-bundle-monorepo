"""Incrementality measurement: did recommendations actually add revenue?

Two things have to be kept apart, and conflating them is what the dashboard was
doing before this existed:

- **Attributed revenue** — orders where a shopper interacted with a
  recommendation. Deterministic, taken from line-item stamps, and what the
  merchant is billed 3% of. It lives in `offer_impressions.revenue_added` and
  `commission_records`.
- **Incremental revenue** — how much *more* those shoppers spent than the
  holdout group who were shown nothing. Statistical, requires a control arm,
  and always smaller than attributed revenue.

`offer_impressions.revenue_added` can never appear in lift math. It only exists
for shoppers who were *shown* an offer, so it has no control counterpart. Trying
to derive a two-arm statistic from one arm's data is exactly why the old code
had to invent a p-value and a confidence interval.

Lift is computed from **order outcomes for both arms**, joined to the shoppers
who were randomised.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select, text

from app.core.database.models.shop import Shop
from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.core.stats import (
    BootstrapResult,
    ProportionTest,
    bootstrap_mean_diff,
    two_proportion_z_test,
)
from app.services.holdout_service import (
    MIN_CONTROL_ORDERS,
    P_VALUE_THRESHOLD,
    HoldoutService,
)

logger = get_logger(__name__)

# Every surface the recommendation API can serve. Kept in step with
# CONTEXT_SURFACE in app/api/v1/recommendations.py.
ALL_SURFACES = ("phoenix", "apollo", "mercury", "thank_you", "venus")


class LiftState(str, Enum):
    """Why we can or cannot report a number.

    Evaluated in this precedence order. The distinction between
    NOT_MEASURABLE and INSUFFICIENT_DATA is the reason this enum exists rather
    than a boolean: a surface at 10% holdout with no control rows *yet* will
    fill up, while one held at 0% never will. Collapsing them would either
    promise a merchant data that is never coming, or imply an unmeasurable
    surface is underperforming.
    """

    #: The merchant switched the holdout off. No control arm exists at all.
    HOLDOUT_DISABLED = "holdout_disabled"
    #: Every requested surface runs at 0% holdout by configuration.
    NOT_MEASURABLE = "not_measurable"
    #: A real holdout, but not yet enough control orders to be reliable.
    INSUFFICIENT_DATA = "insufficient_data"
    #: Powered, and the difference is not distinguishable from zero.
    NOT_SIGNIFICANT = "not_significant"
    #: Powered, and the difference is real.
    SIGNIFICANT = "significant"


@dataclass(frozen=True)
class ShopperRow:
    """One randomised shopper in the analysis window.

    Deliberately DB-free so the exclusion rules and the state machine can be
    tested with plain dataclasses — `python-worker/tests/` has no test database.
    """

    identity: str
    n_impressions: int
    n_bucketed: int
    any_control: bool
    all_control: bool
    n_surfaces: int
    converted: bool
    revenue: float


@dataclass
class Arms:
    """The two experimental arms, plus what was left out and why."""

    treatment_revenue: List[float] = field(default_factory=list)
    control_revenue: List[float] = field(default_factory=list)
    treatment_converters: int = 0
    control_converters: int = 0
    excluded: Dict[str, int] = field(default_factory=dict)

    @property
    def treatment_n(self) -> int:
        return len(self.treatment_revenue)

    @property
    def control_n(self) -> int:
        return len(self.control_revenue)


def partition_shoppers(rows: Iterable[ShopperRow]) -> Arms:
    """Split randomised shoppers into arms, applying every exclusion rule.

    Pure and synchronous on purpose — this is the logic most worth testing and
    it should need nothing but a list of dataclasses.

    The unit is the **shopper**, not the impression. `is_held_out` buckets on
    `md5(shop_id:surface:identity)`, so the unit of analysis has to match the unit of
    randomisation. Impression-level analysis is wrong twice over: treatment
    shoppers accumulate one row per offer while control shoppers are logged once
    per request, so the denominators aren't comparable; and attaching an order's
    revenue to N impressions counts that order N times. The old code did exactly
    that — `treatmentOrders = totalImpressions`.

    Exclusions, in order:

    1. **Never bucketable** — every impression carried `bucketed: false`, so the
       shopper had no stable identity to hash and could never have landed in
       control. Counting them as treatment inflates that arm with people the
       experiment could not have randomised.
    2. **Crossover** — appeared in both arms. Happens when the holdout percent
       changed mid-window, when a shop toggled `holdout_disabled`, or when an
       anonymous session later acquired a customer id and re-bucketed. There is
       no clean counterfactual, so they are dropped rather than forced into an
       arm.

    A *partially* bucketed shopper is kept: they were bucketable at least once,
    so they genuinely could have been control.
    """
    arms = Arms(excluded={"unbucketed": 0, "crossover": 0})

    for row in rows:
        if row.n_bucketed == 0:
            arms.excluded["unbucketed"] += 1
            continue

        if row.any_control != row.all_control:
            arms.excluded["crossover"] += 1
            continue

        if row.all_control:
            arms.control_revenue.append(row.revenue)
            if row.converted:
                arms.control_converters += 1
        else:
            arms.treatment_revenue.append(row.revenue)
            if row.converted:
                arms.treatment_converters += 1

    return arms


@dataclass
class ArmSummary:
    shoppers: int
    converters: int
    conversion_rate: float
    revenue_per_shopper: float
    total_revenue: float
    #: Descriptive only, never given a p-value. AOV is conditional on
    #: converting, so the arms' converter populations differ — that is selection
    #: on the outcome, and no sample size makes the difference causal.
    aov: float


@dataclass
class LiftResult:
    state: LiftState
    treatment: ArmSummary
    control: ArmSummary
    excluded: Dict[str, int]
    surfaces_measurable: List[str]
    surfaces_not_measurable: List[str]
    min_control_orders: int = MIN_CONTROL_ORDERS
    p_value_threshold: float = P_VALUE_THRESHOLD

    # Every statistic is optional and is None in the three unpowered states.
    # The old type made these non-nullable, so something had to be put in them.
    conversion_lift_abs: Optional[float] = None
    conversion_lift_rel: Optional[float] = None
    conversion_lift_rel_lower: Optional[float] = None
    conversion_lift_rel_upper: Optional[float] = None
    p_value: Optional[float] = None

    revenue_per_shopper_delta: Optional[float] = None
    revenue_delta_lower: Optional[float] = None
    revenue_delta_upper: Optional[float] = None
    revenue_p_value: Optional[float] = None

    incremental_revenue: Optional[float] = None
    incremental_revenue_lower: Optional[float] = None
    incremental_revenue_upper: Optional[float] = None


def _summarise(revenue: Sequence[float], converters: int) -> ArmSummary:
    n = len(revenue)
    total = sum(revenue)
    return ArmSummary(
        shoppers=n,
        converters=converters,
        conversion_rate=(converters / n) if n else 0.0,
        revenue_per_shopper=(total / n) if n else 0.0,
        total_revenue=total,
        aov=(total / converters) if converters else 0.0,
    )


def evaluate(
    arms: Arms,
    *,
    holdout_disabled: bool,
    surfaces_measurable: Sequence[str],
    surfaces_not_measurable: Sequence[str],
    seed: int = 0,
) -> LiftResult:
    """Decide the state and, only where it is earned, compute the statistics.

    Pure: takes partitioned arms and configuration, returns a result. The
    ordering of the guards is the honesty guarantee — nothing below can produce
    a number until everything above it has passed.
    """
    treatment = _summarise(arms.treatment_revenue, arms.treatment_converters)
    control = _summarise(arms.control_revenue, arms.control_converters)

    base = dict(
        treatment=treatment,
        control=control,
        excluded=arms.excluded,
        surfaces_measurable=list(surfaces_measurable),
        surfaces_not_measurable=list(surfaces_not_measurable),
    )

    if holdout_disabled:
        return LiftResult(state=LiftState.HOLDOUT_DISABLED, **base)

    if not surfaces_measurable:
        # Configuration, not an observation. Reached only when every requested
        # surface runs at 0% holdout.
        return LiftResult(state=LiftState.NOT_MEASURABLE, **base)

    # Gate on control *converters* — orders — matching the name
    # MIN_CONTROL_ORDERS. Control sessions are the wrong quantity: the binding
    # constraint on precision is how many control shoppers actually bought.
    if arms.control_converters < MIN_CONTROL_ORDERS:
        return LiftResult(state=LiftState.INSUFFICIENT_DATA, **base)

    conversion: ProportionTest = two_proportion_z_test(
        arms.treatment_converters,
        arms.treatment_n,
        arms.control_converters,
        arms.control_n,
    )
    revenue: BootstrapResult = bootstrap_mean_diff(
        arms.treatment_revenue, arms.control_revenue, seed=seed
    )

    # Significance is decided on the conversion p-value alone. The revenue
    # bootstrap is reported alongside but never promotes the state on its own —
    # two metrics each able to declare success is an untracked multiple
    # comparison, and would roughly double the false-positive rate.
    significant = (
        conversion.p_value is not None
        and conversion.p_value < P_VALUE_THRESHOLD
    )

    incremental = None
    incremental_lower = None
    incremental_upper = None
    if revenue.delta_lower is not None and revenue.delta_upper is not None:
        # Per-shopper difference scaled to the treated population. May be
        # negative, and the interval may straddle zero — both are legitimate
        # results that the UI has to be able to render.
        incremental = revenue.delta * arms.treatment_n
        incremental_lower = revenue.delta_lower * arms.treatment_n
        incremental_upper = revenue.delta_upper * arms.treatment_n

    return LiftResult(
        state=LiftState.SIGNIFICANT if significant else LiftState.NOT_SIGNIFICANT,
        conversion_lift_abs=conversion.absolute_diff,
        conversion_lift_rel=conversion.relative_diff,
        conversion_lift_rel_lower=conversion.relative_diff_lower,
        conversion_lift_rel_upper=conversion.relative_diff_upper,
        p_value=conversion.p_value,
        revenue_per_shopper_delta=revenue.delta,
        revenue_delta_lower=revenue.delta_lower,
        revenue_delta_upper=revenue.delta_upper,
        revenue_p_value=revenue.p_value,
        incremental_revenue=incremental,
        incremental_revenue_lower=incremental_lower,
        incremental_revenue_upper=incremental_upper,
        **base,
    )


def eligible_surfaces(shop: Shop, surface: Optional[str] = None) -> tuple:
    """(measurable, not_measurable) for the requested scope.

    A surface is measurable when its holdout percent is above zero — read from
    `HoldoutService.get_holdout_percent`, the same function that produced the
    arm assignment. Deriving it from anywhere else guarantees drift.
    """
    candidates = [surface] if surface else list(ALL_SURFACES)
    measurable, not_measurable = [], []
    for s in candidates:
        if HoldoutService.get_holdout_percent(shop, s) > 0:
            measurable.append(s)
        else:
            not_measurable.append(s)
    return measurable, not_measurable


# One row per randomised shopper. `metadata` is a `json` column (not `jsonb`),
# so `->>` works directly with no cast. A missing `bucketed` key COALESCEs to
# true: rows written before the flag existed *were* bucketed, only the flag is
# absent.
_SHOPPERS_SQL = text(
    """
    WITH elig AS (
        SELECT COALESCE(customer_id, session_id) AS identity,
               is_control,
               surface,
               COALESCE((metadata->>'bucketed')::boolean, true) AS bucketed
        FROM offer_impressions
        WHERE shop_id = :shop_id
          AND created_at >= :start
          AND created_at < :end
          AND surface = ANY(:surfaces)
          AND COALESCE(customer_id, session_id) IS NOT NULL
    )
    SELECT identity,
           COUNT(*)                          AS n_impressions,
           COUNT(*) FILTER (WHERE bucketed)  AS n_bucketed,
           bool_or(is_control)               AS any_control,
           bool_and(is_control)              AS all_control,
           COUNT(DISTINCT surface)           AS n_surfaces
    FROM elig
    GROUP BY identity
    """
)

# Order outcomes, keyed to whichever identity the shopper was randomised on.
#
# Both identity kinds are needed: the impression may have bucketed on a visitor
# id while the order carries a customer id (guest browses, logs in at checkout)
# or the reverse. `DISTINCT ON (order_id)` with customer_id preferred guarantees
# an order is credited to exactly one shopper, so revenue cannot be
# double-counted across arms.
_ORDERS_SQL = text(
    """
    WITH ord AS (
        SELECT order_id, total_amount, currency_code, customer_id, note_attributes
        FROM order_data
        WHERE shop_id = :shop_id
          AND order_date >= :start
          AND order_date < :end
          AND test = false
          AND cancelled_at IS NULL
    ),
    ident AS (
        SELECT order_id, total_amount, currency_code, customer_id AS identity, 0 AS pref
        FROM ord
        WHERE customer_id IS NOT NULL AND customer_id <> ''
        UNION ALL
        SELECT o.order_id, o.total_amount, o.currency_code, a.value, 1
        FROM ord o,
             LATERAL (
                 SELECT COALESCE(e->>'key', e->>'name') AS key, e->>'value' AS value
                 FROM json_array_elements(o.note_attributes) e
             ) a
        WHERE a.key = '_bb_session' AND a.value IS NOT NULL AND a.value <> ''
    )
    SELECT DISTINCT ON (order_id) order_id, identity, total_amount, currency_code
    FROM ident
    ORDER BY order_id, pref
    """
)


async def compute_lift(
    shop_id: str,
    start: datetime,
    end: datetime,
    surface: Optional[str] = None,
) -> LiftResult:
    """Measure lift for a shop over a window, optionally for one surface."""
    async with get_transaction_context() as session:
        shop = (
            await session.execute(select(Shop).where(Shop.id == shop_id))
        ).scalar_one_or_none()
        if shop is None:
            raise ValueError(f"Shop {shop_id} not found")

        measurable, not_measurable = eligible_surfaces(shop, surface)

        # Nothing to query if no surface can be measured — and querying anyway
        # would put treatment-only impressions into an arm.
        if not measurable or shop.holdout_disabled:
            return evaluate(
                Arms(excluded={"unbucketed": 0, "crossover": 0}),
                holdout_disabled=bool(shop.holdout_disabled),
                surfaces_measurable=measurable,
                surfaces_not_measurable=not_measurable,
            )

        shopper_rows = (
            await session.execute(
                _SHOPPERS_SQL,
                {
                    "shop_id": shop_id,
                    "start": start,
                    "end": end,
                    "surfaces": measurable,
                },
            )
        ).all()

        order_rows = (
            await session.execute(
                _ORDERS_SQL,
                {"shop_id": shop_id, "start": start, "end": end},
            )
        ).all()

    shop_currency = (shop.currency_code or "USD").upper()

    # Orders in a different currency are dropped rather than summed at the
    # wrong scale — mixing 5,000 JPY into a USD mean is worse than omitting it.
    revenue_by_identity: Dict[str, float] = {}
    currency_mismatch = 0
    for row in order_rows:
        if (row.currency_code or shop_currency).upper() != shop_currency:
            currency_mismatch += 1
            continue
        key = str(row.identity)
        revenue_by_identity[key] = revenue_by_identity.get(key, 0.0) + float(
            row.total_amount or 0.0
        )

    shoppers = [
        ShopperRow(
            identity=str(r.identity),
            n_impressions=int(r.n_impressions),
            n_bucketed=int(r.n_bucketed),
            any_control=bool(r.any_control),
            all_control=bool(r.all_control),
            n_surfaces=int(r.n_surfaces),
            converted=str(r.identity) in revenue_by_identity,
            revenue=revenue_by_identity.get(str(r.identity), 0.0),
        )
        for r in shopper_rows
    ]

    arms = partition_shoppers(shoppers)
    arms.excluded["currency_mismatch"] = currency_mismatch

    result = evaluate(
        arms,
        holdout_disabled=False,
        surfaces_measurable=measurable,
        surfaces_not_measurable=not_measurable,
        # Seeded from the shop so a merchant reloading sees a stable interval.
        seed=abs(hash(shop_id)) & 0xFFFF,
    )

    logger.info(
        f"📊 Lift for {shop_id} [{surface or 'all'}]: {result.state.value} "
        f"(treatment {arms.treatment_n} shoppers/{arms.treatment_converters} orders, "
        f"control {arms.control_n}/{arms.control_converters}, "
        f"excluded {arms.excluded})"
    )
    return result
