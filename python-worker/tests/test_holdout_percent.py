"""Per-surface holdout rates.
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


def test_every_surface_uses_shop_default():
    """All surfaces use the shop default holdout percent initially."""
    shop = FakeShop()
    for surface in ("phoenix", "apollo", "venus", "mercury", "thank_you"):
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
