"""
Messaging core module for BetterBundle
"""

from .interfaces import Message, MessageBus, MessageProducer, MessageConsumer
from .message_bus import KafkaMessageBus
from .event_publisher import EventPublisher
from .event_subscriber import EventSubscriber

__all__ = [
    "Message",
    "MessageBus",
    "MessageProducer",
    "MessageConsumer",
    "KafkaMessageBus",
    "EventPublisher",
    "EventSubscriber",
]
