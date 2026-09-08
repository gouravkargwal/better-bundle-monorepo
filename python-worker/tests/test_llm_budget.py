"""
Guards on LLM spend.

The behaviour under test is money, so it gets a real test rather than a smoke
check: a permanent error must not be retried, a transient one must be, and the
circuit must open before a failing provider is called indefinitely.
"""

import time

import pytest

from app.recommandations.edges.llm_budget import (
    BudgetExceeded,
    CircuitOpen,
    LLMBudget,
    classify,
)


class FakeRedis:
    """Just enough Redis for the breaker: incr, get, set, delete, expire."""

    def __init__(self):
        self.store = {}

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v):
        self.store[k] = v

    async def delete(self, k):
        self.store.pop(k, None)

    async def incr(self, k):
        self.store[k] = str(int(self.store.get(k, 0)) + 1)
        return int(self.store[k])

    async def expire(self, k, ttl):
        return True


def budget_with(redis, **kw):
    b = LLMBudget(**kw)

    async def _redis():
        return redis

    b._redis = _redis
    return b


# ---------------------------------------------------------------------------
# Error classification — the biggest spend saver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "API key not valid. Please pass a valid API key.",
        "PERMISSION_DENIED: caller does not have permission",
        "400 INVALID_ARGUMENT: request contains an invalid argument",
        "billing account not configured",
    ],
)
def test_permanent_errors_are_not_retried(message):
    assert classify(RuntimeError(message)).retryable is False


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED: Quota exceeded",
        "503 Service Unavailable",
        "deadline exceeded",
        "connection reset by peer",
    ],
)
def test_transient_errors_are_retried(message):
    assert classify(RuntimeError(message)).retryable is True


def test_unknown_errors_are_retried_but_bounded():
    # Retried, because an unrecognised error may well be transient — but it
    # still consumes an attempt, so MAX_ENRICHMENT_ATTEMPTS bounds the cost.
    assert classify(RuntimeError("something new")).retryable is True


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_transient_failures():
    redis = FakeRedis()
    b = budget_with(redis, failure_threshold=3)

    await b.check()  # closed to begin with

    for _ in range(3):
        await b.record_failure(RuntimeError("429 quota exceeded"))

    with pytest.raises(CircuitOpen):
        await b.check()


@pytest.mark.asyncio
async def test_permanent_failures_do_not_open_the_circuit():
    # One shop sending an invalid request says nothing about provider health.
    # Tripping on it would stop enrichment for every other shop.
    redis = FakeRedis()
    b = budget_with(redis, failure_threshold=2)

    for _ in range(5):
        await b.record_failure(RuntimeError("API key not valid"))

    await b.check()  # still closed


@pytest.mark.asyncio
async def test_success_resets_the_failure_count():
    redis = FakeRedis()
    b = budget_with(redis, failure_threshold=3)

    await b.record_failure(RuntimeError("timeout"))
    await b.record_failure(RuntimeError("timeout"))
    await b.record_success()
    await b.record_failure(RuntimeError("timeout"))

    await b.check()  # two failures short of the threshold, so still closed


@pytest.mark.asyncio
async def test_circuit_half_opens_after_the_cooldown():
    redis = FakeRedis()
    b = budget_with(redis, failure_threshold=1, open_seconds=60)

    await b.record_failure(RuntimeError("503 unavailable"))
    with pytest.raises(CircuitOpen):
        await b.check()

    # Pretend the cooldown elapsed.
    redis.store["llm:breaker:opened_at"] = str(time.time() - 61)

    await b.check()  # one probe allowed through
    assert "llm:breaker:opened_at" not in redis.store


# ---------------------------------------------------------------------------
# Daily ceiling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_ceiling_blocks_further_calls():
    redis = FakeRedis()
    b = budget_with(redis, max_calls_per_day=3)

    for _ in range(3):
        await b.check()
        await b.record_call()

    with pytest.raises(BudgetExceeded):
        await b.check()


@pytest.mark.asyncio
async def test_guards_are_inert_without_redis():
    # Redis being down must degrade to "no guards", not "no enrichment".
    b = LLMBudget()

    async def _no_redis():
        return None

    b._redis = _no_redis

    await b.check()
    await b.record_call()
    await b.record_success()
    assert (await b.status()) == {"guards": "unavailable"}
