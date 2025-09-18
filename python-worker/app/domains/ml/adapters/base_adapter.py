"""
Base adapter for interaction events
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseInteractionEventAdapter(ABC):
    """Base adapter for extracting data from interaction events"""

    def __init__(self, event_type: str):
        self.event_type = event_type

    @abstractmethod
    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from event"""
        pass

    @abstractmethod
    def extract_customer_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract customer ID from event"""
        pass

    @abstractmethod
    def extract_timestamp(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from event"""
        pass

    @abstractmethod
    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from event"""
        pass

    def extract_session_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from event"""
        return event.get("sessionId") or event.get("clientId")

    def extract_shop_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract shop ID from event"""
        return event.get("shopId")

    def is_valid_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is valid for this adapter"""
        event_type = event.get("interactionType", event.get("eventType", ""))
        return event_type == self.event_type

    def extract_all_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all relevant data from event"""
        try:
            return {
                "product_id": self.extract_product_id(event),
                "customer_id": self.extract_customer_id(event),
                "timestamp": self.extract_timestamp(event),
                "session_id": self.extract_session_id(event),
                "shop_id": self.extract_shop_id(event),
                "metadata": self.extract_metadata(event),
                "event_type": self.event_type,
            }
        except Exception as e:
            logger.error(
                f"Error extracting data from {self.event_type} event: {str(e)}"
            )
            logger.error(f"Event data: {event}")
            return {}
