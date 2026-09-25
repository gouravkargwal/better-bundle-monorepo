"""The trial ends on evidence and money, not money alone.

Revenue on its own was the wrong gate. On a store with a $1,500 average order
one attributed order clears a $1,000 threshold, so the merchant was asked to
start paying on the strength of a single sale while the Proof page still read
"Not enough data yet". Being billed for a number you cannot check is the exact
complaint that fills competitors' one-star reviews.

These are pure checks on the gate arithmetic - the repository call itself needs
a database and is covered by the billing integration tests.
"""

import pytest

from app.domains.billing.repositories.billing_repository_v2 import MIN_TRIAL_ORDERS

TRIAL_REVENUE_THRESHOLD = 1000


def trial_complete(revenue: float, orders: int) -> bool:
    """The gate, stated once: both conditions or neither."""
    return revenue >= TRIAL_REVENUE_THRESHOLD and orders >= MIN_TRIAL_ORDERS


def test_one_large_order_does_not_end_the_trial():
    """The real case from the stage store: $1,110.20 attributed on one order."""
    assert not trial_complete(revenue=1110.20, orders=1)


def test_many_small_orders_do_not_end_the_trial():
    """The mirror failure: plenty of evidence, almost no money made."""
    assert not trial_complete(revenue=300.0, orders=30)


def test_both_conditions_end_the_trial():
    assert trial_complete(revenue=1000.0, orders=MIN_TRIAL_ORDERS)


def test_the_gate_is_a_conjunction_not_a_disjunction():
    """An OR would reintroduce both failures it exists to prevent."""
    revenue_only = trial_complete(revenue=50_000.0, orders=2)
    orders_only = trial_complete(revenue=10.0, orders=500)
    assert not revenue_only
    assert not orders_only


@pytest.mark.parametrize(
    "revenue,orders,expected",
    [
        (999.99, 30, False),   # a cent short
        (1000.0, 29, False),   # an order short
        (1000.0, 30, True),    # exactly enough
    ],
)
def test_boundaries(revenue, orders, expected):
    assert trial_complete(revenue, orders) is expected


def test_threshold_is_high_enough_to_be_evidence():
    """Guards the reasoning, not the number.

    Below roughly a dozen orders a merchant can still reasonably call it
    coincidence, which defeats the point of waiting at all. If someone lowers
    this to make the trial end sooner, that is a pricing decision and should
    be made deliberately, not by nudging a constant.
    """
    assert MIN_TRIAL_ORDERS >= 12
