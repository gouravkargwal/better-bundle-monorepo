"""Currency conversion for billing.

We charge in USD and measure in every currency. Those are separate decisions:

- Charging is USD because a Shopify app subscription is pinned to one currency
  at creation and cannot be repriced without merchant re-approval. Shopify
  converts our USD charge into the merchant's payout currency and shows them
  the local amount on their own invoice, so the merchant sees local money
  without us maintaining a per-currency price list that drifts out of parity
  every time rates move.

- Measuring must handle any currency, because a Shopify Markets store takes
  several presentment currencies inside one billing cycle. Revenue therefore
  arrives mixed and has to be normalised per order before it can be summed.

Nothing bridged the two. An INR shop attributing 5,000 was charged 3% of
*5000* as *dollars* — about $150 instead of $1.60 — and crossed the $1,000
free-revenue threshold after roughly 1,000 INR, about $10 of real sales. Every
non-USD merchant was over-billed by their FX rate.

Rates come from the `exchange_rates` table, refreshed daily by
`fx_refresher.run_forever()`. `convert_to_usd` returns the rate alongside the
amount so the caller can store it on the charge: a commission re-derived later
with a newer rate would silently restate an invoice the merchant already paid.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models.exchange_rate import ExchangeRate
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)

BILLING_CURRENCY = "USD"

# How stale a rate may be before we stop trusting it. The refresher runs daily,
# so a few days of slack absorbs a transient outage; a fortnight means the job
# has been dead and every amount it prices is drifting.
MAX_RATE_AGE_DAYS = 14


@dataclass(frozen=True)
class Converted:
    """A USD amount and the rate that produced it."""

    amount: Decimal
    rate: Decimal
    source_currency: str


async def convert_to_usd(
    session: AsyncSession,
    amount: Decimal,
    currency: Optional[str],
) -> Optional[Converted]:
    """Convert `amount` from `currency` to USD at the current stored rate.

    Returns None when no usable rate exists. Callers must treat None as "do not
    bill": charging an unconverted amount as USD is the over-billing this
    module exists to prevent.
    """
    code = (currency or BILLING_CURRENCY).upper()
    amount = Decimal(str(amount))

    if code == BILLING_CURRENCY:
        return Converted(amount=amount, rate=Decimal("1"), source_currency=code)

    row = (
        await session.execute(
            select(ExchangeRate).where(ExchangeRate.currency == code)
        )
    ).scalar_one_or_none()

    if row is None:
        logger.error(
            f"💱 No {code} rate stored — refusing to bill rather than charging "
            f"{amount} {code} as dollars. Is the FX refresher running?"
        )
        return None

    age_days = (now_utc() - row.fetched_at).days
    if age_days > MAX_RATE_AGE_DAYS:
        logger.error(
            f"💱 {code} rate is {age_days}d stale (fetched {row.fetched_at}) — "
            f"refusing to bill. The FX refresher is not running."
        )
        return None

    rate = Decimal(str(row.usd_rate))
    if rate <= 0:
        logger.error(f"💱 Unusable {code} rate {rate}")
        return None

    return Converted(
        amount=(amount / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        rate=rate,
        source_currency=code,
    )
