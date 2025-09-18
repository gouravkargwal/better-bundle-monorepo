"""
Centralized Stream Manager for BetterBundle
===========================================

This module provides a centralized way to manage Redis streams and routing.
It implements the Domain-Driven Design pattern for stream management.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

from app.core.redis_client import streams_manager
from app.core.logging import get_logger
from app.shared.constants.redis import (
    # Domain-Specific Streams
    DATA_COLLECTION_STREAM,
    NORMALIZATION_STREAM,
    PURCHASE_ATTRIBUTION_STREAM,
    REFUND_ATTRIBUTION_STREAM,
    REFUND_NORMALIZATION_STREAM,
    SHOPIFY_EVENTS_STREAM,
)

logger = get_logger(__name__)


class StreamType(Enum):
    """Enum for stream types to ensure type safety"""

    DATA_COLLECTION = "data_collection"
    NORMALIZATION = "normalization"
    PURCHASE_ATTRIBUTION = "purchase_attribution"
    REFUND_ATTRIBUTION = "refund_attribution"
    REFUND_NORMALIZATION = "refund_normalization"
    SHOPIFY_EVENTS = "shopify_events"


@dataclass
class StreamConfig:
    """Configuration for a stream"""

    stream_name: str
    description: str
    event_types: List[str]
    is_legacy: bool = False


class StreamManager:
    """
    Centralized stream manager that handles routing and publishing to the correct streams.

    This implements the Domain-Driven Design pattern where each domain has its own stream.
    """

    # Stream configurations
    STREAM_CONFIGS = {
        StreamType.DATA_COLLECTION: StreamConfig(
            stream_name=DATA_COLLECTION_STREAM,
            description="Data collection jobs from Shopify API",
            event_types=["data_collection", "shop_sync", "product_sync", "order_sync"],
        ),
        StreamType.NORMALIZATION: StreamConfig(
            stream_name=NORMALIZATION_STREAM,
            description="Entity normalization jobs",
            event_types=["normalize_entity", "normalize_batch", "normalize_scan"],
        ),
        StreamType.PURCHASE_ATTRIBUTION: StreamConfig(
            stream_name=PURCHASE_ATTRIBUTION_STREAM,
            description="Purchase attribution processing",
            event_types=["purchase_ready_for_attribution", "attribution_calculation"],
        ),
        StreamType.REFUND_ATTRIBUTION: StreamConfig(
            stream_name=REFUND_ATTRIBUTION_STREAM,
            description="Refund attribution processing",
            event_types=["refund_created", "refund_attribution_calculation"],
        ),
        StreamType.REFUND_NORMALIZATION: StreamConfig(
            stream_name=REFUND_NORMALIZATION_STREAM,
            description="Refund normalization processing",
            event_types=["refund_created", "refund_normalization"],
        ),
        StreamType.SHOPIFY_EVENTS: StreamConfig(
            stream_name=SHOPIFY_EVENTS_STREAM,
            description="Raw Shopify webhook events",
            event_types=[
                "product_updated",
                "product_created",
                "order_paid",
                "refund_created",
                "customer_created",
                "customer_updated",
                "collection_created",
                "collection_updated",
            ],
        ),
    }

    def __init__(self):
        self.logger = get_logger(__name__)

    def get_stream_for_event_type(self, event_type: str) -> Optional[str]:
        """
        Get the appropriate stream for an event type.

        Args:
            event_type: The type of event (e.g., 'normalize_entity', 'data_collection')

        Returns:
            The stream name for the event type, or None if not found
        """
        for stream_type, config in self.STREAM_CONFIGS.items():
            if event_type in config.event_types:
                return config.stream_name

        self.logger.error(f"No stream found for event type: {event_type}")
        return None

    def get_stream_for_domain(self, domain: StreamType) -> str:
        """
        Get the stream name for a specific domain.

        Args:
            domain: The domain type

        Returns:
            The stream name for the domain
        """
        if domain not in self.STREAM_CONFIGS:
            raise ValueError(f"Unknown domain: {domain}")

        return self.STREAM_CONFIGS[domain].stream_name

    async def publish_to_domain(
        self, domain: StreamType, event_data: Dict[str, Any]
    ) -> str:
        """
        Publish an event to a specific domain stream.

        Args:
            domain: The domain to publish to
            event_data: The event data to publish

        Returns:
            The message ID
        """
        stream_name = self.get_stream_for_domain(domain)
        self.logger.info(f"Publishing to {domain.value} stream: {stream_name}")
        return await streams_manager.publish_event(stream_name, event_data)

    async def publish_by_event_type(self, event_data: Dict[str, Any]) -> str:
        """
        Publish an event to the appropriate stream based on event type.

        Args:
            event_data: The event data to publish (must contain 'event_type')

        Returns:
            The message ID
        """
        event_type = event_data.get("event_type")
        if not event_type:
            raise ValueError("Event data must contain 'event_type' field")

        stream_name = self.get_stream_for_event_type(event_type)
        if not stream_name:
            raise ValueError(f"No stream found for event type: {event_type}")

        self.logger.info(f"Publishing {event_type} to stream: {stream_name}")
        return await streams_manager.publish_event(stream_name, event_data)

    def get_all_streams(self) -> Dict[StreamType, StreamConfig]:
        """Get all stream configurations"""
        return self.STREAM_CONFIGS

    def get_active_streams(self) -> Dict[StreamType, StreamConfig]:
        """Get all stream configurations"""
        return self.STREAM_CONFIGS


# Global instance
stream_manager = StreamManager()
