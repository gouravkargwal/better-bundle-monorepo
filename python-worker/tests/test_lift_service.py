"""Exclusion rules and the honest-state machine.

Pure tests over dataclasses — no database, matching the style of
`test_holdout_percent.py`. These cover the rules that decide whether a merchant
is shown a number at all, which is the part most worth pinning down: the code
this replaces reported "statistically significant" whenever revenue was above
zero and ten control rows existed.
"""

from dataclasses import dataclass

from app.services.holdout_service import MIN_CONTROL_ORDERS, P_VALUE_THRESHOLD
from app.services.lift_service import (
    Arms,
    LiftState,
    ShopperRow,
    eligible_surfaces,
    evaluate,
    partition_shoppers,
)


@dataclass
class FakeShop:
    holdout_disabled: bool = False


def shopper(
    identity="s1",
    n_impressions=1,
    n_bucketed=1,
    any_control=False,
    all_control=False,
    n_surfaces=1,
    converted=False,
    revenue=0.0,
):
    return ShopperRow(
        identity=identity,
        n_impressions=n_impressions,
        n_bucketed=n_bucketed,
        any_control=any_control,
        all_control=all_control,
        n_surfaces=n_surfaces,
        converted=converted,
        revenue=revenue,
    )


def arms_with(control_converters: int, treatment_converters: int = 500) -> Arms:
    """Arms sized so the statistics are computable, for state-machine tests."""
    rows = []
    for i in range(10_000):
        rows.append(
            shopper(
                identity=f"t{i}",
                converted=i < treatment_converters,
                revenue=50.0 if i < treatment_converters else 0.0,
            )
        )
    for i in range(10_000):
        rows.append(
            shopper(
                identity=f"c{i}",
                any_control=True,
                all_control=True,
                converted=i < control_converters,
                revenue=50.0 if i < control_converters else 0.0,
            )
        )
    return partition_shoppers(rows)


# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------


def test_unbucketed_shoppers_are_excluded_from_both_arms():
    """They could never have been control, so they cannot be treatment either.

    A shopper with no stable identity was never randomised. Counting them as
    treatment fills that arm with people the experiment could not have assigned,
    which biases the comparison. Both arms are checked so the test fails if the
    filter is applied to only one.
    """
    rows = [
        shopper(identity="t-unbucketed", n_bucketed=0, revenue=100.0),
        shopper(
            identity="c-unbucketed",
            n_bucketed=0,
            any_control=True,
            all_control=True,
            revenue=90.0,
        ),
        shopper(identity="t-ok", revenue=10.0),
    ]

    arms = partition_shoppers(rows)

    assert arms.excluded["unbucketed"] == 2
    assert arms.treatment_revenue == [10.0]
    assert arms.control_revenue == []


def test_partially_bucketed_shopper_is_kept_once():
    """Bucketable at least once means they genuinely could have been control."""
    arms = partition_shoppers(
        [shopper(n_impressions=5, n_bucketed=2, converted=True, revenue=75.0)]
    )

    assert arms.excluded["unbucketed"] == 0
    assert arms.treatment_revenue == [75.0]
    assert arms.treatment_converters == 1


def test_crossover_shopper_is_excluded():
    """In both arms at once — no clean counterfactual, so drop and count."""
    arms = partition_shoppers(
        [shopper(any_control=True, all_control=False, revenue=40.0)]
    )

    assert arms.excluded["crossover"] == 1
    assert arms.treatment_revenue == []
    assert arms.control_revenue == []


def test_shopper_with_many_impressions_counts_once():
    """The direct regression test for `treatmentOrders = totalImpressions`.

    400 impressions and one $100 order is one observation of $100, not 400.
    """
    arms = partition_shoppers(
        [shopper(n_impressions=400, n_bucketed=400, converted=True, revenue=100.0)]
    )

    assert arms.treatment_revenue == [100.0]
    assert arms.treatment_converters == 1
    assert arms.treatment_n == 1


def test_non_converting_shoppers_stay_in_the_denominator():
    """Revenue-per-shopper needs the zeros; dropping them inflates both arms."""
    arms = partition_shoppers(
        [
            shopper(identity="a", converted=True, revenue=100.0),
            shopper(identity="b"),
            shopper(identity="c"),
        ]
    )

    assert arms.treatment_n == 3
    assert arms.treatment_revenue == [100.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


def test_holdout_disabled_outranks_everything():
    result = evaluate(
        arms_with(control_converters=500),
        holdout_disabled=True,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state is LiftState.HOLDOUT_DISABLED
    assert result.p_value is None
    assert result.incremental_revenue is None


def test_no_measurable_surface_is_not_measurable():
    result = evaluate(
        Arms(excluded={}),
        holdout_disabled=False,
        surfaces_measurable=[],
        surfaces_not_measurable=["mercury", "thank_you"],
    )

    assert result.state is LiftState.NOT_MEASURABLE
    assert result.p_value is None


def test_below_min_control_orders_is_insufficient_data():
    """Even a huge apparent lift must not be reported under-powered."""
    result = evaluate(
        arms_with(control_converters=MIN_CONTROL_ORDERS - 1),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state is LiftState.INSUFFICIENT_DATA
    assert result.p_value is None
    assert result.incremental_revenue is None
    # Counts are still reported so the UI can show progress toward the gate.
    assert result.control.converters == MIN_CONTROL_ORDERS - 1
    assert result.min_control_orders == MIN_CONTROL_ORDERS


def test_at_min_control_orders_statistics_are_computed():
    result = evaluate(
        arms_with(control_converters=MIN_CONTROL_ORDERS, treatment_converters=500),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state in (LiftState.SIGNIFICANT, LiftState.NOT_SIGNIFICANT)
    assert result.p_value is not None
    assert result.conversion_lift_rel is not None


def test_a_real_lift_is_significant_and_carries_an_interval():
    """5% vs 1% conversion on 10,000 each — unambiguous."""
    result = evaluate(
        arms_with(control_converters=100, treatment_converters=500),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state is LiftState.SIGNIFICANT
    assert result.p_value is not None and result.p_value < P_VALUE_THRESHOLD
    assert result.incremental_revenue is not None
    assert result.incremental_revenue_lower is not None
    assert result.conversion_lift_rel is not None and result.conversion_lift_rel > 0


def test_no_real_difference_is_not_significant():
    """Identical arms must never be promoted to significant."""
    result = evaluate(
        arms_with(control_converters=500, treatment_converters=500),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state is LiftState.NOT_SIGNIFICANT
    assert result.p_value is not None and result.p_value >= P_VALUE_THRESHOLD


def test_no_control_converters_at_all_is_insufficient_not_significant():
    """Today's real state: a control arm exists but nobody in it has bought.

    This is what the engine returns until the `_bb_session` cart attribute is
    flowing on orders, and it must read as "collecting", never as a result.
    """
    result = evaluate(
        arms_with(control_converters=0, treatment_converters=500),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.state is LiftState.INSUFFICIENT_DATA
    assert result.p_value is None


def test_aov_is_reported_but_never_as_a_lift():
    """AOV is conditional on converting, so its difference is not causal.

    Per-arm AOV is useful description; there is deliberately no aov_lift field
    anywhere on the result.
    """
    result = evaluate(
        arms_with(control_converters=100, treatment_converters=500),
        holdout_disabled=False,
        surfaces_measurable=["phoenix"],
        surfaces_not_measurable=[],
    )

    assert result.treatment.aov == 50.0
    assert result.control.aov == 50.0
    assert not hasattr(result, "aov_lift")
    assert not hasattr(result, "aov_lift_percent")


# ---------------------------------------------------------------------------
# Surface eligibility comes from the holdout service, not from observation
# ---------------------------------------------------------------------------


def test_all_surfaces_are_measurable_by_default():
    measurable, not_measurable = eligible_surfaces(FakeShop())

    assert not_measurable == []
    assert "mercury" in measurable
    assert "thank_you" in measurable
    assert "phoenix" in measurable
    assert "apollo" in measurable
    assert "venus" in measurable


def test_a_single_requested_surface_is_measurable():
    measurable, not_measurable = eligible_surfaces(FakeShop(), surface="mercury")

    assert measurable == ["mercury"]
    assert not_measurable == []


def test_an_eligible_surface_is_measurable_even_with_no_data_yet():
    """The distinction that matters: phoenix will fill up, mercury never will."""
    measurable, _ = eligible_surfaces(FakeShop(), surface="phoenix")

    assert measurable == ["phoenix"]


def test_holdout_disabled_shop_has_no_measurable_surface():
    measurable, not_measurable = eligible_surfaces(FakeShop(holdout_disabled=True))

    assert measurable == []
    assert len(not_measurable) == 5
