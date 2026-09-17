"""The per-placement breakdown the merchant dashboard reads.

Guards the two bugs that made it wrong: keying by extension instead of
placement (which hid every thank-you-page sale under Checkout), and a dict
comprehension that dropped all but the last offer per key.
"""

from decimal import Decimal

from app.domains.billing.models.attribution_models import (
    AttributionBreakdown,
    AttributionType,
    ExtensionType,
)
from app.domains.billing.services.attribution_engine import AttributionEngine


def _row(surface: str, extension: ExtensionType, amount: str) -> AttributionBreakdown:
    return AttributionBreakdown(
        extension_type=extension,
        product_id=f"p-{surface}-{amount}",
        attributed_amount=Decimal(amount),
        attribution_weight=1.0,
        attribution_type=AttributionType.DIRECT_CLICK,
        interaction_id=f"i-{surface}-{amount}",
        metadata={"surface": surface},
    )


def test_thank_you_is_its_own_placement_not_checkout():
    # Both ship inside the mercury extension; they are separate placements.
    revenue, interactions = AttributionEngine._by_surface(
        [
            _row("thank_you", ExtensionType.MERCURY, "40.00"),
            _row("mercury", ExtensionType.MERCURY, "10.00"),
        ]
    )
    assert revenue == {"thank_you": 40.00, "mercury": 10.00}
    assert interactions == {"thank_you": 1, "mercury": 1}


def test_multiple_offers_on_one_placement_are_summed():
    breakdown = [
        _row("phoenix", ExtensionType.PHOENIX, "30.00"),
        _row("phoenix", ExtensionType.PHOENIX, "12.50"),
        _row("venus", ExtensionType.VENUS, "7.50"),
    ]
    revenue, interactions = AttributionEngine._by_surface(breakdown)

    assert revenue == {"phoenix": 42.50, "venus": 7.50}
    assert interactions == {"phoenix": 2, "venus": 1}
    # The breakdown must account for every cent the merchant is charged on.
    total = sum(b.attributed_amount for b in breakdown)
    assert round(sum(revenue.values()), 2) == float(total)


if __name__ == "__main__":
    test_thank_you_is_its_own_placement_not_checkout()
    test_multiple_offers_on_one_placement_are_summed()
    print("ok")
