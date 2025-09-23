"""
Event subscriber for consuming domain events
"""

import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Callable
from .interfaces import MessageConsumer, Message, EventHandler, EventFilter
from ..kafka.consumer import KafkaConsumer

logger = logging.getLogger(__name__)


class EventSubscriber:
    """Event subscriber for consuming domain events"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._consumer: Optional[KafkaConsumer] = None
        self._handlers: List[EventHandler] = []
        self._filters: List[EventFilter] = []
        self._initialized = False

    async def initialize(self, topics: List[str], group_id: str):
        """Initialize event subscriber"""
        try:
            self._consumer = KafkaConsumer(self.config)
            await self._consumer.initialize(topics, group_id)
            self._initialized = True
            logger.info(
                f"Event subscriber initialized for topics: {topics}, group: {group_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize event subscriber: {e}")
            raise

    def add_handler(self, handler: EventHandler):
        """Add event handler"""
        self._handlers.append(handler)
        logger.info(f"Added event handler: {handler.__class__.__name__}")

    def add_filter(self, filter_obj: EventFilter):
        """Add event filter"""
        self._filters.append(filter_obj)
        logger.info(f"Added event filter: {filter_obj.__class__.__name__}")

    async def subscribe(
        self, topics: List[str], group_id: str
    ) -> AsyncIterator[Message]:
        """Subscribe to topics and yield messages"""
        if not self._initialized:
            await self.initialize(topics, group_id)

        try:
            async for kafka_message in self._consumer.consume():
                # Convert to our Message format
                message = Message(
                    topic=kafka_message["topic"],
                    key=kafka_message["key"],
                    value=kafka_message["value"],
                    headers=kafka_message.get("headers", {}),
                    partition=kafka_message["partition"],
                    offset=kafka_message["offset"],
                    timestamp=kafka_message["timestamp"],
                    message_id=kafka_message.get("message_id"),
                )

                # Apply filters
                if not self._should_process(message):
                    continue

                yield message

        except Exception as e:
            logger.error(f"Error in subscription to {topics}: {e}")
            raise

    def _should_process(self, message: Message) -> bool:
        """Check if message should be processed based on filters"""
        for filter_obj in self._filters:
            if not filter_obj.should_process(message):
                return False
        return True

    async def handle_message(self, message: Message) -> bool:
        """Handle a single message with registered handlers"""
        try:
            event_type = message.value.get("event_type")
            if not event_type:
                logger.warning(f"No event_type in message: {message.message_id}")
                return False

            # Find appropriate handlers
            handlers = [h for h in self._handlers if h.can_handle(event_type)]

            if not handlers:
                logger.warning(f"No handlers for event type: {event_type}")
                return True  # Not an error, just no handlers

            # Process with handlers
            success = True
            for handler in handlers:
                try:
                    handler_success = await handler.handle(message.value)
                    if not handler_success:
                        success = False
                        logger.error(
                            f"Handler {handler.__class__.__name__} failed for event {event_type}"
                        )
                except Exception as e:
                    success = False
                    logger.error(
                        f"Handler {handler.__class__.__name__} error for event {event_type}: {e}"
                    )

            return success

        except Exception as e:
            logger.error(f"Error handling message {message.message_id}: {e}")
            return False

    async def consume_and_handle(self, topics: List[str], group_id: str):
        """Consume messages and handle them automatically"""
        try:
            async for message in self.subscribe(topics, group_id):
                try:
                    success = await self.handle_message(message)
                    if success:
                        await self._consumer.commit(message)
                        logger.debug(
                            f"Message {message.message_id} handled and committed"
                        )
                    else:
                        logger.error(
                            f"Message {message.message_id} handling failed, not committing"
                        )
                except Exception as e:
                    logger.exception(
                        f"Error processing message {message.message_id}: {e}"
                    )
        except Exception as e:
            logger.exception(f"Error in consume_and_handle for topics {topics}: {e}")
            raise

    async def close(self):
        """Close event subscriber"""
        if self._consumer:
            await self._consumer.close()
        self._initialized = False
        logger.info("Event subscriber closed")
