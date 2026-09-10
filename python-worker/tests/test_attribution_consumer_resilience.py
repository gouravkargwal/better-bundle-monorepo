"""A bad message must never stall the attribution topic.

One order whose `session_id` violated a foreign key froze the entire
attribution pipeline: the handler raised, the old code logged and `continue`d
without committing, so the offset never advanced. Every restart replayed the
same failure and every order queued behind it starved — no attributions, no
commissions, and nothing in the logs explaining why.

The contract these tests pin down is narrow and absolute: **the offset always
ends up committed.** A transient fault gets a few retries; a permanent one gets
dead-lettered. Either way the partition moves on.
"""

import pytest

from app.consumers.kafka.purchase_attribution_consumer import (
    MAX_PROCESSING_ATTEMPTS,
    PurchaseAttributionKafkaConsumer,
)

pytestmark = pytest.mark.asyncio


class _FakeConsumer:
    def __init__(self):
        self.commits = []

    async def commit(self, message=None):
        self.commits.append(message)
        return True


class _FakeDLQ:
    def __init__(self, explode=False):
        self.sent = []
        self.explode = explode

    async def send_to_dlq(self, **kwargs):
        if self.explode:
            raise RuntimeError("DLQ is down")
        self.sent.append(kwargs)
        return True


def _consumer(handler, dlq_explodes=False):
    c = PurchaseAttributionKafkaConsumer.__new__(PurchaseAttributionKafkaConsumer)
    c.consumer = _FakeConsumer()
    c.dlq_service = _FakeDLQ(explode=dlq_explodes)
    c._handle_message = handler
    return c


MESSAGE = {"value": {"event_type": "purchase_ready_for_attribution", "order_id": "1"}}


async def test_success_commits_once():
    calls = []

    async def handler(msg):
        calls.append(msg)

    c = _consumer(handler)
    await c._process_with_retry(MESSAGE)

    assert len(calls) == 1
    assert len(c.consumer.commits) == 1
    assert c.dlq_service.sent == []


async def test_transient_failure_is_retried_then_succeeds(monkeypatch):
    """A database blip should not cost the order its attribution."""
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    attempts = []

    async def handler(msg):
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("connection reset")

    c = _consumer(handler)
    await c._process_with_retry(MESSAGE)

    assert len(attempts) == 2
    assert len(c.consumer.commits) == 1, "must commit after the retry succeeds"
    assert c.dlq_service.sent == [], "a recovered message is not a dead letter"


async def test_permanent_failure_is_dead_lettered_and_still_commits(monkeypatch):
    """The bug this file exists for: the offset must advance regardless.

    Without the commit the partition is stuck forever and every later order is
    starved behind one bad row.
    """
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    attempts = []

    async def handler(msg):
        attempts.append(1)
        raise RuntimeError("ForeignKeyViolationError: session_id not present")

    c = _consumer(handler)
    await c._process_with_retry(MESSAGE)

    assert len(attempts) == MAX_PROCESSING_ATTEMPTS, "bounded, not infinite"
    assert len(c.consumer.commits) == 1, "POISON MESSAGE STALLED THE PARTITION"
    assert len(c.dlq_service.sent) == 1
    assert c.dlq_service.sent[0]["reason"] == "processing_failed"


async def test_commit_happens_even_if_the_dlq_write_fails(monkeypatch):
    """The DLQ is a convenience; unblocking the partition is not optional."""
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    async def handler(msg):
        raise RuntimeError("permanent")

    c = _consumer(handler, dlq_explodes=True)
    await c._process_with_retry(MESSAGE)

    assert len(c.consumer.commits) == 1, "a broken DLQ must not re-block the topic"


async def _no_sleep(_seconds):
    return None
