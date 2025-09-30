"""
Trigger a customer linking Kafka event from the command line.

Usage examples:

  python -m app.scripts.trigger_customer_linking \
    --shop-id <SHOP_ID> \
    --customer-id <CUSTOMER_ID> \
    --session-id <SESSION_ID>

If --session-id is omitted, it will still publish the job without a trigger session.
"""

import asyncio
import os
import sys
import time
from typing import Optional


python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_publisher import EventPublisher


def _build_job_id(shop_id: str, customer_id: str, session_id: Optional[str]) -> str:
    ts = int(time.time())
    base = f"customer_linking_{shop_id}_{customer_id}_{ts}"
    return f"{base}_{session_id}" if session_id else base


async def _run(shop_id: str, customer_id: str, session_id: Optional[str]) -> None:
    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()

    try:
        job_id = _build_job_id(shop_id, customer_id, session_id)
        linking_event = {
            "job_id": job_id,
            "shop_id": shop_id,
            "customer_id": customer_id,
            "event_type": "customer_linking",
            "trigger_session_id": session_id,
            "linked_sessions": None,
            "metadata": {
                "session_id": session_id,
                "source": "manual_trigger_script",
            },
        }

        message_id = await publisher.publish_customer_linking_event(linking_event)
        print(
            f"Published customer linking job. job_id={job_id} message_id={message_id}"
        )
    finally:
        await publisher.close()


def main() -> None:
    asyncio.run(
        _run(
            "cmg6eft3h0000v3nggxv6oxmf",
            "8667833041035",
            "unified_1759227468401_038miqu92",
        )
    )


if __name__ == "__main__":
    main()
