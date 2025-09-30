"""
Messaging interfaces and abstract base classes
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """Standard message format"""

    topic: str
    key: Optional[str]
    value: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None
    partition: Optional[int] = None
    offset: Optional[int] = None
    timestamp: Optional[int] = None
    message_id: Optional[str] = None


class MessageBus(ABC):
    """Abstract message bus interface"""

    @abstractmethod
    async def publish(self, message: Message) -> str:
        """Publish a message and return message ID"""
        pass

    @abstractmethod
    async def subscribe(
        self, topics: List[str], group_id: str
    ) -> AsyncIterator[Message]:
        """Subscribe to topics and yield messages"""
        pass

    @abstractmethod
    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message processing"""
        pass


class MessageProducer(ABC):
    """Abstract producer interface"""

    @abstractmethod
    async def send(
        self, topic: str, message: Dict[str, Any], key: Optional[str] = None
    ) -> str:
        """Send message to topic"""
        pass

    @abstractmethod
    async def send_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Send multiple messages"""
        pass


class MessageConsumer(ABC):
    """Abstract consumer interface"""

    @abstractmethod
    async def consume(self, topics: List[str], group_id: str) -> AsyncIterator[Message]:
        """Consume messages from topics"""
        pass

    @abstractmethod
    async def commit(self, message_id: str) -> bool:
        """Commit message offset"""
        pass


class EventHandler(ABC):
    """Abstract event handler interface"""

    @abstractmethod
    async def handle(self, event: Dict[str, Any]) -> bool:
        """Handle an event and return success status"""
        pass

    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can handle the event type"""
        pass


class EventFilter(ABC):
    """Abstract event filter interface"""

    @abstractmethod
    def should_process(self, message: Message) -> bool:
        """Determine if message should be processed"""
        pass


class MessageSerializer(ABC):
    """Abstract message serializer interface"""

    @abstractmethod
    def serialize(self, message: Dict[str, Any]) -> bytes:
        """Serialize message to bytes"""
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize bytes to message"""
        pass


class MessageValidator(ABC):
    """Abstract message validator interface"""

    @abstractmethod
    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate message format and content"""
        pass

    @abstractmethod
    def get_errors(self, message: Dict[str, Any]) -> List[str]:
        """Get validation errors for message"""
        pass
