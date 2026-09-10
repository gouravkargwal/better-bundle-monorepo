"""Current USD exchange rates used to denominate commissions.

Attributed revenue arrives in whatever the shopper paid in; commissions and
Shopify usage records are USD. Rates live here rather than in source so they
can be refreshed without a deploy.

One row per currency — the latest rate, not a history. Attribution runs within
minutes of the order, so the current rate *is* the order's rate, and the rate
that priced a charge is copied onto the commission row itself
(`CommissionRecord.fx_rate`). That keeps every past invoice reproducible
without this table carrying a date dimension nothing would read.
"""

from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import TIMESTAMP

from .base import BaseModel


class ExchangeRate(BaseModel):
    """Units of `currency` per 1 USD."""

    __tablename__ = "exchange_rates"

    currency = Column(String(3), nullable=False, unique=True, index=True)

    # Units of `currency` per 1 USD, e.g. INR 87.00. Wide precision because
    # low-denomination currencies (IDR, VND) need it, and rounding the rate
    # rather than the converted amount compounds across a billing cycle.
    usd_rate = Column(Numeric(20, 10), nullable=False)

    fetched_at = Column(TIMESTAMP(timezone=True), nullable=False)
    source = Column(String(50), nullable=False, default="ecb")

    def __repr__(self) -> str:
        return f"<ExchangeRate({self.currency}={self.usd_rate} per USD)>"
