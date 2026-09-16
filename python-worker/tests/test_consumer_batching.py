"""Checks for the concurrent batching in the data collection consumer.

Guards the two ways batching goes wrong: a partial batch stalling until more
traffic arrives, and committing an offset before every message in the batch
has actually finished.
"""

import asyncio
import sys
import types


class FakeConsumer:
    """Yields queued messages, then blocks — like a quiet topic."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.committed = []

    async def consume(self):
        for m in self._messages:
            yield m
        # Topic goes quiet rather than ending.
        await asyncio.Event().wait()

    async def commit(self, message):
        self.committed.append(message["offset"])


def build_consumer(messages, handler):
    from app.consumers.kafka.data_collection_consumer import (
        DataCollectionKafkaConsumer,
    )

    c = DataCollectionKafkaConsumer.__new__(DataCollectionKafkaConsumer)
    c.consumer = FakeConsumer(messages)
    c._initialized = True
    c.MAX_CONCURRENT_MESSAGES = 10
    c.BATCH_WAIT_SECONDS = 0.1
    c._handle_message = handler
    return c


def msg(offset):
    return {"topic": "shopify-events", "partition": 0, "offset": offset}


async def test_partial_batch_flushes_without_more_traffic():
    """A batch smaller than the limit must not wait for messages that never come."""
    seen = []

    async def handler(m):
        seen.append(m["offset"])

    c = build_consumer([msg(1), msg(2), msg(3)], handler)
    task = asyncio.create_task(c.start_consuming())
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert seen == [1, 2, 3], f"partial batch stalled, only saw {seen}"
    assert c.consumer.committed == [3], f"expected commit at 3, got {c.consumer.committed}"


async def test_commit_waits_for_slowest_message():
    """The offset must not be committed while a message in the batch is unfinished."""
    finished = []

    async def handler(m):
        # Message 1 is slow; message 2 is fast.
        await asyncio.sleep(0.3 if m["offset"] == 1 else 0.0)
        finished.append(m["offset"])

    c = build_consumer([msg(1), msg(2)], handler)
    task = asyncio.create_task(c.start_consuming())
    await asyncio.sleep(1.0)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert sorted(finished) == [1, 2], f"not all messages ran: {finished}"
    assert c.consumer.committed == [2], f"expected commit at 2, got {c.consumer.committed}"


async def test_one_failure_does_not_sink_the_batch():
    """A raising message is logged, and the rest of the batch still commits."""
    ran = []

    async def handler(m):
        ran.append(m["offset"])
        if m["offset"] == 1:
            raise RuntimeError("boom")

    c = build_consumer([msg(1), msg(2)], handler)
    task = asyncio.create_task(c.start_consuming())
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert sorted(ran) == [1, 2]
    assert c.consumer.committed == [2]


class TricklingConsumer(FakeConsumer):
    """A topic that keeps delivering, with gaps longer than the batch window.

    This is the shape that exposed the cancellation bug: applying the batch
    timeout directly to the consumer iterator cancelled an in-flight fetch on
    every idle gap, so throughput collapsed and messages were lost.
    """

    async def consume(self):
        for m in self._messages:
            await asyncio.sleep(0.15)  # longer than BATCH_WAIT_SECONDS below
            yield m
        await asyncio.Event().wait()


async def test_slow_stream_loses_nothing():
    seen = []

    async def handler(m):
        seen.append(m["offset"])

    from app.consumers.kafka.data_collection_consumer import (
        DataCollectionKafkaConsumer,
    )

    c = DataCollectionKafkaConsumer.__new__(DataCollectionKafkaConsumer)
    c.consumer = TricklingConsumer([msg(i) for i in range(1, 9)])
    c._initialized = True
    c.MAX_CONCURRENT_MESSAGES = 10
    c.BATCH_WAIT_SECONDS = 0.1  # shorter than the inter-message gap
    c._handle_message = handler

    task = asyncio.create_task(c.start_consuming())
    await asyncio.sleep(2.5)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert sorted(seen) == list(range(1, 9)), f"messages lost or stalled: {sorted(seen)}"
    assert c.consumer.committed, "nothing was ever committed"


async def main():
    await test_partial_batch_flushes_without_more_traffic()
    await test_commit_waits_for_slowest_message()
    await test_one_failure_does_not_sink_the_batch()
    await test_slow_stream_loses_nothing()
    print("consumer batching checks passed")


if __name__ == "__main__":
    asyncio.run(main())
