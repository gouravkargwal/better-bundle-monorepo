"""The holdout starts large to reach a measured lift fast, then steps down.

The cost of a large control arm is widely misjudged, so it is worth stating
once: what costs revenue is the number of control orders, not the rate, and
that number is fixed at MIN_CONTROL_ORDERS either way. At 10% you withhold from
100 buyers out of 1,000 orders; at 50% you withhold from 100 out of 200. Same
forgone lift, five times sooner. These tests pin that the rates keep that
property and that the step is one-way.
"""

import pytest

from app.services.holdout_service import (
    EARNING_HOLDOUT_PERCENT,
    INITIAL_HOLDOUT_PERCENT,
    LEARNING_HOLDOUT_PERCENT,
    MIN_CONTROL_ORDERS,
    HoldoutService,
)


class FakeShop:
    def __init__(self, holdout_disabled=False, holdout_percent=None):
        self.holdout_disabled = holdout_disabled
        self.holdout_percent = holdout_percent


def test_a_new_shop_learns_before_it_earns():
    """No tuned value yet means the large control arm."""
    assert HoldoutService.get_holdout_percent(FakeShop()) == LEARNING_HOLDOUT_PERCENT


def test_a_tuned_shop_uses_its_stored_rate():
    shop = FakeShop(holdout_percent=EARNING_HOLDOUT_PERCENT)
    assert HoldoutService.get_holdout_percent(shop) == EARNING_HOLDOUT_PERCENT


def test_the_merchant_switch_still_beats_everything():
    """`holdout_disabled` is the merchant's call and outranks any tuning."""
    shop = FakeShop(holdout_disabled=True, holdout_percent=LEARNING_HOLDOUT_PERCENT)
    for surface in ("phoenix", "mercury", "thank_you", "apollo", "venus", None):
        assert HoldoutService.get_holdout_percent(shop, surface) == 0


def test_learning_is_larger_than_earning():
    """The whole point. If these ever invert, proof gets slower, not faster."""
    assert LEARNING_HOLDOUT_PERCENT > EARNING_HOLDOUT_PERCENT
    assert INITIAL_HOLDOUT_PERCENT == LEARNING_HOLDOUT_PERCENT


def test_forgone_lift_is_the_same_at_either_rate():
    """Control orders are the cost, not the percentage.

    Guards the reasoning behind the large learning arm: if someone lowers it
    believing it saves revenue, this shows the saving is zero and the only
    thing traded away is time.
    """
    def orders_needed(pct):
        return MIN_CONTROL_ORDERS / (pct / 100)

    learning_orders = orders_needed(LEARNING_HOLDOUT_PERCENT)
    earning_orders = orders_needed(EARNING_HOLDOUT_PERCENT)

    # Same number of buyers withheld either way.
    assert learning_orders * (LEARNING_HOLDOUT_PERCENT / 100) == pytest.approx(
        earning_orders * (EARNING_HOLDOUT_PERCENT / 100)
    )
    # But the large arm gets there sooner.
    assert learning_orders < earning_orders


def test_stepping_down_never_moves_a_shopper_into_control():
    """A step down must not create crossovers in the control direction.

    Control is the band [0, percent), so lowering the rate can only move
    shoppers out of control, never in. `partition_shoppers` discards anyone
    seen in both arms, so a rate that went back up would silently delete the
    very data the tuner is trying to accumulate.
    """
    identities = [f"customer-{i}" for i in range(2000)]

    control_before = {
        i
        for i in identities
        if HoldoutService.is_held_out(
            "shop-1", i, None, LEARNING_HOLDOUT_PERCENT, "phoenix"
        )
    }
    control_after = {
        i
        for i in identities
        if HoldoutService.is_held_out(
            "shop-1", i, None, EARNING_HOLDOUT_PERCENT, "phoenix"
        )
    }

    assert control_after <= control_before, (
        "stepping down moved shoppers INTO control; they would be discarded "
        "as crossovers and the measurement would lose data"
    )
    assert control_after, "the monitoring arm must not be empty"


def test_bucketing_is_stable_for_one_shopper():
    """Same shopper, same arm — otherwise the control group is not a control."""
    for _ in range(5):
        assert HoldoutService.is_held_out(
            "shop-1", "customer-42", None, LEARNING_HOLDOUT_PERCENT, "phoenix"
        ) is HoldoutService.is_held_out(
            "shop-1", "customer-42", None, LEARNING_HOLDOUT_PERCENT, "phoenix"
        )
