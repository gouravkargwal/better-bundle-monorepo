"""Per-surface holdout rates.

A holdout costs the merchant real revenue: a held-out shopper is deliberately
shown no offer. That price is worth paying only when the resulting control group
is large enough to measure something. Checkout and thank-you became bucketable
before they had that volume, so their rate is pinned at zero until they do.

These tests exist to stop the zero being "fixed" by accident, and to keep the
merchant's own kill switch absolute.
"""

from dataclasses import dataclass

from app.services.holdout_service import (
    INITIAL_HOLDOUT_PERCENT,
    SURFACE_HOLDOUT_PERCENT,
    HoldoutService,
)


@dataclass
class FakeShop:
    holdout_disabled: bool = False


def test_merchant_switch_overrides_every_surface():
    """`holdout_disabled` is the merchant's decision and outranks our defaults."""
    shop = FakeShop(holdout_disabled=True)
    for surface in ("phoenix", "mercury", "thank_you", "apollo", "venus", None):
        assert HoldoutService.get_holdout_percent(shop, surface) == 0


def test_checkout_and_thank_you_are_not_held_out_yet():
    """Withholding offers at the payment step buys ~2 control sessions today."""
    shop = FakeShop()
    assert HoldoutService.get_holdout_percent(shop, "mercury") == 0
    assert HoldoutService.get_holdout_percent(shop, "thank_you") == 0


def test_other_surfaces_keep_the_shop_default():
    """Phoenix is already collecting a usable control group; don't disturb it."""
    shop = FakeShop()
    for surface in ("phoenix", "apollo", "venus"):
        assert (
            HoldoutService.get_holdout_percent(shop, surface)
            == INITIAL_HOLDOUT_PERCENT
        )


def test_omitting_surface_gives_the_shop_wide_rate():
    """Kept optional so pre-existing callers behave exactly as before."""
    assert HoldoutService.get_holdout_percent(FakeShop()) == INITIAL_HOLDOUT_PERCENT


def test_an_unknown_surface_does_not_silently_disable_the_experiment():
    """A new surface should inherit the default, not fall through to zero."""
    assert (
        HoldoutService.get_holdout_percent(FakeShop(), "some_new_surface")
        == INITIAL_HOLDOUT_PERCENT
    )


def test_overrides_are_valid_percentages():
    for surface, percent in SURFACE_HOLDOUT_PERCENT.items():
        assert isinstance(percent, int), surface
        assert 0 <= percent <= 100, surface
