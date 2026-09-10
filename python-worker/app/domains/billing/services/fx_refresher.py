"""Daily refresh of the `exchange_rates` table.

Two keyless sources, tried in order:

  1. open.er-api.com — USD-based, 166 currencies, covers Shopify's full
     presentment list. Community-run, so no availability guarantee.
  2. Frankfurter — official ECB reference rates, about 30 currencies. Narrower
     but authoritative; enough to keep the major markets billable.

Neither needs an API key. We make one call a day and keep the last good rates,
so an outage is harmless until it lasts longer than `fx.MAX_RATE_AGE_DAYS`, at
which point conversion starts refusing to bill rather than using stale numbers.

A failed refresh never clears existing rates — the upsert only ever writes
values it actually fetched.
"""

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Dict

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.core.database.models.exchange_rate import ExchangeRate
from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)

REFRESH_INTERVAL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 20

SOURCES = (
    ("er-api", "https://open.er-api.com/v6/latest/USD"),
    ("ecb", "https://api.frankfurter.app/latest?from=USD"),
)


def _parse_rates(payload: dict) -> Dict[str, Decimal]:
    """Both sources expose USD-based rates under `rates`.

    Values are coerced through `str` because JSON floats cannot represent a
    rate exactly and Decimal(float) would carry the binary error into money.
    """
    raw = payload.get("rates") or {}
    rates: Dict[str, Decimal] = {}
    for code, value in raw.items():
        if not isinstance(code, str) or len(code) != 3:
            continue
        try:
            rate = Decimal(str(value))
        except (InvalidOperation, TypeError):
            continue
        if rate > 0:
            rates[code.upper()] = rate
    # USD against itself is 1 by definition; er-api includes it, ECB does not.
    rates["USD"] = Decimal("1")
    return rates


async def _fetch() -> tuple[str, Dict[str, Decimal]]:
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for source, url in SOURCES:
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                rates = _parse_rates(response.json())
                if len(rates) < 2:
                    raise ValueError(f"{source} returned no usable rates")
                return source, rates
            except Exception as e:  # noqa: BLE001 - try the next source
                last_error = e
                logger.warning(f"💱 FX source {source} failed: {e}")
    raise RuntimeError(f"All FX sources failed; last error: {last_error}")


async def refresh_once() -> int:
    """Fetch and upsert rates. Returns the number of currencies written."""
    source, rates = await _fetch()
    fetched_at = now_utc()

    async with get_transaction_context() as session:
        for code, rate in rates.items():
            stmt = insert(ExchangeRate).values(
                currency=code,
                usd_rate=rate,
                fetched_at=fetched_at,
                source=source,
            )
            # `currency` is unique; a refresh overwrites in place rather than
            # accumulating a row per day.
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[ExchangeRate.currency],
                    set_={
                        "usd_rate": stmt.excluded.usd_rate,
                        "fetched_at": stmt.excluded.fetched_at,
                        "source": stmt.excluded.source,
                    },
                )
            )

    logger.info(f"💱 Refreshed {len(rates)} FX rates from {source}")
    return len(rates)


async def run_forever() -> None:
    """Refresh at startup, then daily.

    The startup refresh matters: on a fresh database the table is empty, and
    without it every non-USD shop would be unbillable until the first interval
    elapsed a day later.
    """
    while True:
        try:
            await refresh_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a dead refresher must not kill the app
            logger.error(f"💱 FX refresh failed, keeping existing rates: {e}")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
