"""
Spend safeguards for LLM calls.

A retry loop plus a paid API is a way to lose money quietly. Three independent
guards, because each stops a different failure:

1. Error classification — never retry what cannot succeed.
   A 401, or a request the model rejects as malformed, will fail identically
   forever. Retrying it four times over four hours costs four calls and buys
   nothing. Only timeouts, 429s and 5xx are worth another attempt.

2. Circuit breaker — when the provider is down, stop asking.
   Quota exhaustion is the dangerous case: every shop's sweep independently
   discovers it, so the failure count multiplies by shop instead of being
   recognised once. After `FAILURE_THRESHOLD` consecutive failures the circuit
   opens and calls short-circuit locally for `OPEN_SECONDS` without touching
   the network. One probe is allowed through after that (half-open); success
   closes it, failure re-opens it.

3. Daily call ceiling — a hard stop that does not depend on the other two
   being correct. Even if classification mislabels something and the breaker
   never trips, the day's spend is bounded.

State lives in Redis, not in the process: the sweeper, the webhook path and the
install path all call the same provider, and a per-process breaker would let
three workers each discover the outage separately.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# ── Circuit breaker ────────────────────────────────────────────────────────
FAILURE_THRESHOLD = 5      # consecutive retryable failures before opening
OPEN_SECONDS = 900         # 15 minutes of not calling at all

# ── Daily ceiling ──────────────────────────────────────────────────────────
# Sized against the enrichment workload: 20 products per call means 500 calls
# covers a 10,000-product catalog, which is far more than a day's real churn.
# It exists to bound a runaway, not to shape normal usage.
MAX_CALLS_PER_DAY = 500

_KEY_FAILURES = "llm:breaker:failures"
_KEY_OPENED_AT = "llm:breaker:opened_at"
_KEY_CALLS = "llm:calls"  # suffixed with the UTC date


class BudgetExceeded(RuntimeError):
    """The daily call ceiling has been reached."""


class CircuitOpen(RuntimeError):
    """The provider is failing; calls are being short-circuited."""


@dataclass(frozen=True)
class ErrorClass:
    retryable: bool
    reason: str


# Substrings that identify a permanent failure. Matched against the string form
# of the exception because the provider SDK raises several unrelated types for
# what is operationally the same thing.
_PERMANENT_MARKERS = (
    "api key not valid",
    "api_key_invalid",
    "permission denied",
    "permission_denied",
    "unauthenticated",
    "invalid argument",
    "invalid_argument",
    "not found",
    "unsupported",
    "billing",
)

_RETRYABLE_MARKERS = (
    "quota",
    "rate limit",
    "resource_exhausted",
    "429",
    "500",
    "502",
    "503",
    "504",
    "deadline",
    "timeout",
    "timed out",
    "unavailable",
    "internal error",
    "connection",
)


def classify(error: BaseException) -> ErrorClass:
    """Decide whether an error is worth another attempt.

    Unknown errors are treated as retryable but they still consume an attempt
    and still count towards the breaker, so an unrecognised permanent failure
    costs at most MAX_ENRICHMENT_ATTEMPTS rather than forever.
    """
    text = f"{type(error).__name__}: {error}".lower()

    for marker in _PERMANENT_MARKERS:
        if marker in text:
            return ErrorClass(retryable=False, reason=f"permanent ({marker})")

    for marker in _RETRYABLE_MARKERS:
        if marker in text:
            return ErrorClass(retryable=True, reason=f"transient ({marker})")

    # A parse failure means the model answered but not usefully. Worth one more
    # go — enrichment.py already retries the parse once — but not indefinitely.
    if "json" in text or "validation" in text or "unparseable" in text:
        return ErrorClass(retryable=True, reason="bad model output")

    return ErrorClass(retryable=True, reason="unclassified")


class LLMBudget:
    """Redis-backed breaker and daily ceiling, shared across workers."""

    def __init__(
        self,
        failure_threshold: int = FAILURE_THRESHOLD,
        open_seconds: int = OPEN_SECONDS,
        max_calls_per_day: int = MAX_CALLS_PER_DAY,
    ):
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.max_calls_per_day = max_calls_per_day

    async def _redis(self):
        try:
            return await get_redis_client()
        except Exception as e:
            # Redis being unavailable must not block enrichment entirely, but
            # it does mean the guards are off — say so rather than failing open
            # in silence.
            logger.warning(f"LLM budget guards unavailable (no Redis): {e}")
            return None

    async def check(self) -> None:
        """Raise if a call must not be made. Call before every request."""
        redis = await self._redis()
        if redis is None:
            return

        opened_at = await redis.get(_KEY_OPENED_AT)
        if opened_at:
            elapsed = time.time() - float(opened_at)
            if elapsed < self.open_seconds:
                raise CircuitOpen(
                    f"LLM circuit open for another "
                    f"{int(self.open_seconds - elapsed)}s"
                )
            # Half-open: let this one through as a probe. Clearing the marker
            # first means a concurrent caller does not also probe.
            await redis.delete(_KEY_OPENED_AT)
            logger.info("LLM circuit half-open, probing with one call")

        used = int(await redis.get(self._calls_key()) or 0)
        if used >= self.max_calls_per_day:
            raise BudgetExceeded(
                f"LLM daily ceiling reached ({used}/{self.max_calls_per_day})"
            )

    async def record_call(self) -> None:
        """Count a call against today's ceiling."""
        redis = await self._redis()
        if redis is None:
            return
        key = self._calls_key()
        count = await redis.incr(key)
        if count == 1:
            # 48h so the key outlives the day it counts, then expires itself.
            await redis.expire(key, 172_800)

    async def record_success(self) -> None:
        """Reset the consecutive-failure count."""
        redis = await self._redis()
        if redis is None:
            return
        await redis.delete(_KEY_FAILURES)

    async def record_failure(self, error: BaseException) -> ErrorClass:
        """Count a failure and open the circuit if the provider looks down.

        A permanent error does not count towards the breaker: an invalid
        request for one product says nothing about provider health, and
        tripping on it would stop enrichment for every other shop.
        """
        classification = classify(error)
        if not classification.retryable:
            return classification

        redis = await self._redis()
        if redis is None:
            return classification

        failures = await redis.incr(_KEY_FAILURES)
        if failures == 1:
            await redis.expire(_KEY_FAILURES, self.open_seconds)

        if failures >= self.failure_threshold:
            await redis.set(_KEY_OPENED_AT, str(time.time()))
            await redis.delete(_KEY_FAILURES)
            logger.error(
                f"LLM circuit opened after {failures} consecutive failures; "
                f"pausing all calls for {self.open_seconds}s"
            )

        return classification

    async def status(self) -> dict:
        """For the ops endpoint: is anything currently held back, and why."""
        redis = await self._redis()
        if redis is None:
            return {"guards": "unavailable"}

        opened_at = await redis.get(_KEY_OPENED_AT)
        used = int(await redis.get(self._calls_key()) or 0)
        return {
            "circuit": "open" if opened_at else "closed",
            "circuit_reopens_in": (
                max(0, int(self.open_seconds - (time.time() - float(opened_at))))
                if opened_at
                else 0
            ),
            "consecutive_failures": int(await redis.get(_KEY_FAILURES) or 0),
            "calls_today": used,
            "calls_remaining_today": max(0, self.max_calls_per_day - used),
        }

    @staticmethod
    def _calls_key() -> str:
        return f"{_KEY_CALLS}:{time.strftime('%Y-%m-%d', time.gmtime())}"
